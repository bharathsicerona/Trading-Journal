import imaplib
import email
import os
from email.header import decode_header
import pandas as pd
from datetime import datetime, timedelta
import re
import pdfplumber
import time
import logging
from typing import List
from dotenv import load_dotenv

load_dotenv()

# Import configuration (contains sensitive credentials)
import config
from config import EMAIL_ACCOUNT, APP_PASSWORD, EMAIL_SENDERS, PDF_FOLDER, MAX_EMAILS_PER_SENDER
# Import PDF parsing functions
from pdf_parser import (
    extract_text_from_pdf, parse_trades, extract_trade_date,
    extract_funds_data, extract_pledges_data, extract_account_summary
)

# Helper: determine broker from metadata
def detect_broker_from_metadata(filename: str, sender: str = "", subject: str = "") -> str:
    fn = (filename or '').lower()
    snd = (sender or '').lower()
    
    # 1. High confidence matches based on sender (most reliable)
    if 'mstock' in snd or 'm-stock' in snd or 'm.stock' in snd or 'mirae' in snd:
        return 'mStock'
    if 'groww' in snd:
        return 'Groww'
    if 'exness' in snd:
        return 'Exness'
        
    # 2. Fallback to filename heuristics
    if any(k in fn for k in ['mstock', 'm-stock', 'comm_contract']):
        return 'mStock'
    if 'groww' in fn or 'contract_note' in fn or 'contract note' in fn:
        return 'Groww'
    if 'exness' in fn:
        return 'Exness'
    return 'Unknown'

# Helper: tag filename with broker prefix
def tag_filename_with_broker(folder: str, filename: str, broker: str) -> str:
    name, ext = os.path.splitext(filename)
    safe_broker = broker.replace(' ', '_') if broker else 'Unknown'
    tagged = f"{safe_broker}__{name}{ext}"
    return os.path.join(folder, tagged)

# Module logger; application configures logging
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
IMAP_SERVER = "imap.gmail.com"

# Get the Trading_Automation directory
trading_dir = os.getcwd()
pdf_folder = os.path.join(trading_dir, PDF_FOLDER)

# Create pdfs folder if it doesn't exist
if not os.path.exists(pdf_folder):
    os.makedirs(pdf_folder)

# CSV file paths
trades_csv = os.path.join(trading_dir, "trades.csv")
funds_csv = os.path.join(trading_dir, "funds_transactions.csv")
pledges_csv = os.path.join(trading_dir, "pledges.csv")
account_summary_csv = os.path.join(trading_dir, "account_summary.csv")

logger.info(f"Saving PDFs to: {pdf_folder}")
logger.info("Data files: trades.csv, funds_transactions.csv, pledges.csv, account_summary.csv")

# ===== GMAIL DOWNLOAD FUNCTIONS =====
def download_pdfs_from_gmail(max_retries: int = 3, retry_delay: int = 5, days_back: int = 30, max_emails: int = None, since_date: str = None, before_date: str = None) -> List[str]:
    """Download PDFs from Gmail for specified senders with retry logic"""
    downloaded_files: List[str] = []
    senders = EMAIL_SENDERS
    if max_emails is None:
        max_emails = MAX_EMAILS_PER_SENDER

    for sender in senders:
        logger.info(f"\n[SEARCH] Searching for emails from {sender}...")
        mail = None

        for attempt in range(max_retries):
            try:
                # Connect to Gmail
                mail = imaplib.IMAP4_SSL(IMAP_SERVER, timeout=30)
                mail.login(EMAIL_ACCOUNT, APP_PASSWORD)
                mail.select("inbox")
                logger.info(f"[SUCCESS] Connected to Gmail (attempt {attempt + 1})")

                # Build search query
                if 'mstock' in sender.lower() or 'mirae' in sender.lower():
                    from_clause = '(OR FROM "mstock" FROM "mirae asset")'
                else:
                    from_clause = f'FROM "{sender}"'

                if since_date:
                    search_query = f'{from_clause} SINCE "{since_date}"'
                else:
                    date_filter = (datetime.now() - timedelta(days=days_back)).strftime("%d-%b-%Y")
                    search_query = f'{from_clause} SINCE "{date_filter}"'
                    
                if before_date:
                    search_query += f' BEFORE "{before_date}"'

                status, messages = mail.search(None, search_query)

                if status != "OK" or not messages[0]:
                    logger.info(f"  [INFO] No recent emails found from {sender}")
                    break

                email_ids = messages[0].split()
                # Limit to specified number to prevent timeouts
                email_ids = email_ids[-max_emails:] if len(email_ids) > max_emails else email_ids
                logger.info(f"  [INFO] Found {len(email_ids)} recent emails to process")

                processed_count = 0
                for idx, e_id in enumerate(email_ids):
                    try:
                        # Reconnect every 10 emails to avoid timeout
                        if idx > 0 and idx % 10 == 0:
                            logger.info(f"  [INFO] Reconnecting to Gmail... ({idx}/{len(email_ids)})")
                            try:
                                mail.logout()
                            except Exception:
                                logger.debug("Error logging out while reconnecting, continuing")
                            mail = imaplib.IMAP4_SSL(IMAP_SERVER, timeout=30)
                            mail.login(EMAIL_ACCOUNT, APP_PASSWORD)
                            mail.select("inbox")

                        # Fetch email
                        res, msg_data = mail.fetch(e_id, "(RFC822)")
                        if res != "OK":
                            logger.error(f"  [ERROR] Failed to fetch email {e_id.decode()}")
                            continue

                        for response_part in msg_data:
                            if isinstance(response_part, tuple):
                                msg = email.message_from_bytes(response_part[1])

                            # Extract Subject
                            subject = ""
                            raw_subject = msg.get("Subject")
                            if raw_subject:
                                decoded_list = decode_header(raw_subject)
                                for decoded_str, charset in decoded_list:
                                    if isinstance(decoded_str, bytes):
                                        subject += decoded_str.decode(charset or "utf-8", errors="ignore")
                                    else:
                                        subject += str(decoded_str)

                            # Extract Sender
                            sender_address = ""
                            raw_sender = msg.get("From")
                            if raw_sender:
                                decoded_list = decode_header(raw_sender)
                                for decoded_str, charset in decoded_list:
                                    if isinstance(decoded_str, bytes):
                                        sender_address += decoded_str.decode(charset or "utf-8", errors="ignore")
                                    else:
                                        sender_address += str(decoded_str)

                                for part in msg.walk():
                                    if part.get_content_maintype() == "multipart":
                                        continue

                                    filename = part.get_filename()

                                    if filename:
                                        # Decode filename if needed
                                        filename, encoding = decode_header(filename)[0]
                                        if isinstance(filename, bytes):
                                            filename = filename.decode(encoding if encoding else "utf-8")

                                        # Only download Contract Notes
                                        is_contract = (
                                            any(keyword in filename.lower() for keyword in ['contract', 'note', 'statement', 'comm_contract']) or
                                            any(keyword in subject.lower() for keyword in ['contract', 'note', 'statement', 'comm_contract', 'digital', 'm.stock', 'mirae'])
                                        )

                                        if filename.lower().endswith('.pdf') and is_contract:

                                            filepath = os.path.join(pdf_folder, filename)

                                            # Skip if already exists
                                            if os.path.exists(filepath):
                                                logger.info(f"  [SKIP] Skipping existing file: {filename}")
                                                continue

                                            # Download attachment
                                            attachment_data = part.get_payload(decode=True)
                                            if attachment_data:
                                                # Determine broker from filename or email sender
                                                broker_detected = detect_broker_from_metadata(filename, sender_address, subject)
                                                # Save to a tagged filename to include broker
                                                tagged_path = tag_filename_with_broker(pdf_folder, filename, broker_detected)
                                                # Avoid overwrite by appending timestamp if needed
                                                if os.path.exists(tagged_path):
                                                    base, ext = os.path.splitext(tagged_path)
                                                    tagged_path = f"{base}_{int(time.time())}{ext}"
                                                with open(tagged_path, "wb") as f:
                                                    f.write(attachment_data)

                                                file_size = len(attachment_data) / 1024  # KB
                                                logger.info(f"  [DOWNLOAD] Downloaded: {os.path.basename(tagged_path)} ({file_size:.1f} KB)")
                                                downloaded_files.append(tagged_path)
                                                processed_count += 1

                                                # Record metadata for future reference
                                                processed_csv = os.path.join(trading_dir, 'processed_files.csv')
                                                try:
                                                    row = {'Filename': os.path.basename(tagged_path), 'Broker': broker_detected, 'Source': sender, 'DownloadedAt': datetime.now().isoformat(), 'SizeKB': round(file_size,1)}
                                                    if os.path.exists(processed_csv):
                                                        dfp = pd.read_csv(processed_csv)
                                                        dfp = pd.concat([dfp, pd.DataFrame([row])], ignore_index=True)
                                                    else:
                                                        dfp = pd.DataFrame([row])
                                                    dfp.to_csv(processed_csv, index=False)
                                                except Exception as e:
                                                    logger.debug(f"Could not write processed_files.csv: {e}")

                    except Exception as e:
                        logger.exception(f"  [ERROR] Error processing email {idx + 1}: {str(e)}")
                        continue

                logger.info(f"  [SUCCESS] Processed {processed_count} PDFs from {sender}")
                break  # Success, exit retry loop

            except imaplib.IMAP4.error as e:
                logger.error(f"  [ERROR] IMAP error (attempt {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    logger.info(f"  [INFO] Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    logger.error(f"  [ERROR] Failed to process {sender} after {max_retries} attempts")

            except Exception as e:
                logger.exception(f"  [ERROR] Unexpected error (attempt {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                else:
                    logger.error(f"  [ERROR] Failed to process {sender}")

            finally:
                if mail:
                    try:
                        mail.logout()
                    except Exception:
                        logger.debug("Error during logout in finally block")

    logger.info(f"\nOK Gmail sync complete! Downloaded {len(downloaded_files)} new files")
    return downloaded_files


def parse_new_pdfs(pdf_files: List[str]):
    """Parse newly downloaded PDFs and extract all data"""
    if not pdf_files:
        logger.info("\nNo new PDFs to parse")
        # But still process existing PDFs if no new ones
        pdf_paths = [os.path.join(pdf_folder, f) for f in os.listdir(pdf_folder) if f.endswith('.pdf') and 'contract' in f.lower()]
        if not pdf_paths:
            return
        logger.info(f"Processing {len(pdf_paths)} existing PDFs...")
    else:
        pdf_paths = pdf_files

    logger.info("\nParsing PDFs...")
    new_trades = []
    all_funds = []
    all_pledges = []
    all_summaries = []

    for idx, pdf_path in enumerate(pdf_paths):
        try:
            if not os.path.exists(pdf_path):
                logger.warning(f"  SKIP {idx+1}. File not found: {pdf_path}")
                continue

            filename = os.path.basename(pdf_path)

            # Determine broker directly from the tagged filename prefix
            if '__' in filename:
                broker = filename.split('__')[0].replace('_', ' ')
            else:
                broker = detect_broker_from_metadata(filename)

            pdf_password = None
            if broker in ["Groww", "mStock"]:
                pdf_password = os.getenv("BROKER_PDF_PASSWORD")
                if not pdf_password and hasattr(config, 'BROKER_PDF_PASSWORD'):
                    pdf_password = config.BROKER_PDF_PASSWORD

            text = extract_text_from_pdf(pdf_path, password=pdf_password)
            trade_date = extract_trade_date(text)

            # Fallback: Extract date from filename if text extraction fails or pattern missing
            if not trade_date:
                # Try format like 17-Mar-2026
                m1 = re.search(r'(\d{1,2}-[A-Za-z]{3}-\d{4})', filename, re.IGNORECASE)
                if m1:
                    try:
                        trade_date = datetime.strptime(m1.group(1).title(), '%d-%b-%Y').date()
                        logger.debug(f"Extracted date from filename: {trade_date}")
                    except Exception:
                        pass
            if not trade_date:
                # Try format like 20260317
                m2 = re.search(r'(20\d{6})', filename)
                if m2:
                    try:
                        trade_date = datetime.strptime(m2.group(1), '%Y%m%d').date()
                        logger.debug(f"Extracted date from filename: {trade_date}")
                    except Exception:
                        pass

            if trade_date:
                # Extract trades
                trades = parse_trades(text, trade_date, broker)
                new_trades.extend(trades)
                logger.info(f"  OK {idx+1}. {filename}: {len(trades)} trades")

                # Extract funds
                funds = extract_funds_data(text, trade_date, broker)
                all_funds.extend(funds)
                if funds:
                    logger.info(f"      -> {len(funds)} fund transactions")

                # Extract pledges
                pledges = extract_pledges_data(text, trade_date, broker)
                all_pledges.extend(pledges)
                if pledges:
                    logger.info(f"      -> {len(pledges)} pledge records")

                # Extract summary
                summary = extract_account_summary(text, trade_date, broker, filename)
                all_summaries.append(summary)

            else:
                logger.warning(f"  SKIP {idx+1}. {filename}: Could not extract date")
        except Exception as e:
            logger.exception(f"  ERROR {idx+1}. Error processing {os.path.basename(pdf_path)}: {str(e)}")

    # Save trades
    if new_trades:
        if os.path.exists(trades_csv):
            df_existing = pd.read_csv(trades_csv)
            df_new = pd.DataFrame(new_trades)
            df = pd.concat([df_existing, df_new], ignore_index=True)
            df = df.drop_duplicates(subset=['Date', 'Underlying', 'Strike', 'Type', 'Buy/Sell', 'Quantity', 'WAP', 'Net Total'], keep='first')
        else:
            df = pd.DataFrame(new_trades)
        df.to_csv(trades_csv, index=False)
        logger.info(f"\nOK trades.csv: {len(df)} trades")

    # Save funds transactions
    if all_funds:
        if os.path.exists(funds_csv):
            df_existing = pd.read_csv(funds_csv)
            df_new = pd.DataFrame(all_funds)
            df = pd.concat([df_existing, df_new], ignore_index=True)
            df = df.drop_duplicates(subset=['Date', 'Broker', 'Type', 'Amount'], keep='first')
        else:
            df = pd.DataFrame(all_funds)
        df.to_csv(funds_csv, index=False)
        logger.info(f"OK funds_transactions.csv: {len(df)} transactions")
    else:
        logger.info("SKIP No fund transaction data found in PDFs")

    # Save pledges (even if empty)
    if all_pledges:
        if os.path.exists(pledges_csv):
            df_existing = pd.read_csv(pledges_csv)
            df_new = pd.DataFrame(all_pledges)
            df = pd.concat([df_existing, df_new], ignore_index=True)
        else:
            df = pd.DataFrame(all_pledges)
        df.to_csv(pledges_csv, index=False)
        logger.info(f"OK pledges.csv: {len(df)} pledge records")
    else:
        # Create empty pledges CSV with headers for consistency
        if not os.path.exists(pledges_csv):
            pd.DataFrame(columns=['Date', 'Broker', 'Amount', 'Description']).to_csv(pledges_csv, index=False)
        logger.info("SKIP No pledge data found (created empty file if needed)")

    # Save account summary
    if all_summaries:
        if os.path.exists(account_summary_csv):
            df_existing = pd.read_csv(account_summary_csv)
            df_new = pd.DataFrame(all_summaries)
            df = pd.concat([df_existing, df_new], ignore_index=True)
        else:
            df = pd.DataFrame(all_summaries)
        df.to_csv(account_summary_csv, index=False)
        logger.info(f"OK account_summary.csv: {len(df)} summaries")

# ===== MAIN =====
if __name__ == "__main__":
    # Configure logging for the application
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')

    logger.info("=" * 50)
    logger.info("TRADING JOURNAL - Gmail PDF Fetcher & Parser")
    logger.info("=" * 50)

    # Download PDFs from Gmail
    downloaded_pdfs = download_pdfs_from_gmail()

    # Parse and add to trades.csv
    parse_new_pdfs(downloaded_pdfs)

    logger.info("\n" + "=" * 50)
    logger.info("All tasks complete!")
    logger.info("=" * 50)
