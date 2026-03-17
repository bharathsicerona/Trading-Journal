import imaplib
import email
import os
from email.header import decode_header
import pandas as pd
from datetime import datetime
import re
import pdfplumber

# Import configuration (contains sensitive credentials)
from config import EMAIL_ACCOUNT, APP_PASSWORD, EMAIL_SENDERS, PDF_FOLDER, MAX_EMAILS_PER_SENDER

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

print(f"Saving PDFs to: {pdf_folder}")
print(f"Data files: trades.csv, funds_transactions.csv, pledges.csv, account_summary.csv")

# ===== GMAIL DOWNLOAD FUNCTIONS =====
def download_pdfs_from_gmail():
    """Download PDFs from Gmail for specified senders"""
    print("\nConnecting to Gmail...")
    downloaded_files = []
    senders = EMAIL_SENDERS

    for sender in senders:
        print(f"\nSearching for emails from {sender}...")
        try:
            mail = imaplib.IMAP4_SSL(IMAP_SERVER, timeout=30)
            mail.login(EMAIL_ACCOUNT, APP_PASSWORD)
            mail.select("inbox")
            print("OK Connected to Gmail")
            
            # Search for recent emails from sender (last 30 days to avoid processing too many)
            status, messages = mail.search(None, f'FROM "{sender}" SINCE 15-Feb-2026')
            
            if status != "OK" or not messages[0]:
                print(f"  No recent emails found from {sender}")
                mail.logout()
                continue

            email_ids = messages[0].split()
            # Limit to configured number of emails per sender to prevent timeouts
            email_ids = email_ids[-MAX_EMAILS_PER_SENDER:] if len(email_ids) > MAX_EMAILS_PER_SENDER else email_ids
            print(f"  Found {len(email_ids)} recent emails to process")
            
            for idx, e_id in enumerate(email_ids):
                try:
                    # Reconnect every 10 emails to avoid timeout
                    if idx > 0 and idx % 10 == 0:
                        print(f"  Reconnecting to Gmail... ({idx}/{len(email_ids)})")
                        mail.logout()
                        mail = imaplib.IMAP4_SSL(IMAP_SERVER, timeout=30)
                        mail.login(EMAIL_ACCOUNT, APP_PASSWORD)
                        mail.select("inbox")
                    
                    res, msg_data = mail.fetch(e_id, "(RFC822)")
                    for response_part in msg_data:
                        if isinstance(response_part, tuple):
                            msg = email.message_from_bytes(response_part[1])
                            
                            for part in msg.walk():
                                if part.get_content_maintype() == "multipart":
                                    continue
                                if part.get("Content-Disposition") is None:
                                    continue
                                    
                                filename = part.get_filename()
                                
                                if filename:
                                    filename, encoding = decode_header(filename)[0]
                                    if isinstance(filename, bytes):
                                        filename = filename.decode(encoding if encoding else "utf-8")
                                    
                                    # Only download Contract Notes
                                    if filename.lower().endswith('.pdf') and 'contract' in filename.lower():
                                        filepath = os.path.join(pdf_folder, filename)
                                        
                                        if os.path.exists(filepath):
                                            continue
                                        
                                        with open(filepath, "wb") as f:
                                            f.write(part.get_payload(decode=True))
                                        print(f"  OK Downloaded: {filename}")
                                        downloaded_files.append(filepath)
                except Exception as e:
                    print(f"  WARN Skipping email {e_id}: {str(e)[:50]}")
                    continue
            
            mail.logout()
        except Exception as e:
            print(f"  ERROR Error with {sender}: {e}")
            continue

    print(f"\nOK Gmail sync complete! Downloaded {len(downloaded_files)} new files")
    return downloaded_files

# ===== PDF PARSING FUNCTIONS (from parse_trades.py) =====
def extract_text_from_pdf(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        text = ""
        for page in pdf.pages:
            text += page.extract_text() + "\n"
    return text

def parse_trades(text, trade_date, broker="Unknown"):
    trades = []
    lines = text.split('\n')
    in_trades_section = False
    for line in lines:
        line = line.strip()
        if 'Buy(B)/Sell(S)' in line:
            in_trades_section = True
            continue
        if in_trades_section and line.startswith(('NSE', 'BSE')):
            parts = line.split()
            if len(parts) >= 13:
                exchange = parts[0]
                underlying = parts[1]
                strike = parts[2]
                option_type = parts[3]
                expiry_str = ' '.join(parts[4:7])
                try:
                    expiry = datetime.strptime(expiry_str, '%d %b %Y').date()
                except:
                    continue
                bs = parts[7]
                qty = int(parts[8])
                wap = float(parts[9])
                brokerage = float(parts[10])
                net_price = float(parts[11])
                net_total = float(parts[12])
                trade = {
                    'Date': trade_date,
                    'Exchange': exchange,
                    'Underlying': underlying,
                    'Strike': float(strike),
                    'Type': option_type,
                    'Expiry': expiry,
                    'Buy/Sell': bs,
                    'Quantity': qty,
                    'WAP': wap,
                    'Brokerage': brokerage,
                    'Net Price': net_price,
                    'Net Total': net_total,
                    'Broker': broker
                }
                trades.append(trade)
        if 'Future &' in line and 'Options' in line:
            in_trades_section = False
    return trades

def extract_trade_date(text):
    match = re.search(r'Trade Date (\d{2}-\d{2}-\d{4})', text)
    if match:
        return datetime.strptime(match.group(1), '%d-%m-%Y').date()
    return None

# ===== FUNDS EXTRACTION FUNCTIONS =====
def extract_funds_data(text, trade_date, broker):
    """Extract deposit/withdrawal information"""
    funds = []
    lines = text.split('\n')
    
    for line in lines:
        line = line.strip()
        
        # Extract Pay In / Pay Out
        if 'Pay In / Pay Out Obligation' in line:
            # Match pattern: "Pay In / Pay Out Obligation (before Brokerage) -1030.25 -1030.25"
            parts = line.split()
            if len(parts) >= 2:
                try:
                    # Last number is the amount
                    amount = float(parts[-1])
                    if amount != 0:
                        funds.append({
                            'Date': trade_date,
                            'Broker': broker,
                            'Type': 'Deposit' if amount > 0 else 'Withdrawal',
                            'Amount': abs(amount),
                            'Currency': 'USD' if broker == 'Exness' else 'INR',
                            'Description': 'Settlement Obligation'
                        })
                except (ValueError, IndexError):
                    pass
        
        # Extract Net Amount Receivable/Payable
        if 'Net Amount Receivable' in line or 'Net Amount Payable' in line:
            parts = line.split()
            if len(parts) >= 2:
                try:
                    amount = float(parts[-1])
                    if amount != 0:
                        funds.append({
                            'Date': trade_date,
                            'Broker': broker,
                            'Type': 'Settlement Payable' if amount < 0 else 'Settlement Receivable',
                            'Amount': abs(amount),
                            'Currency': 'USD' if broker == 'Exness' else 'INR',
                            'Description': 'Final Settlement Amount'
                        })
                except (ValueError, IndexError):
                    pass
    
    return funds

def extract_pledges_data(text, trade_date, broker):
    """Extract pledge/collateral information"""
    pledges = []
    
    lines = text.split('\n')
    
    # Look for pledge-related keywords
    for line in lines:
        line = line.strip()
        
        # Pattern: Pledge/Collateral usage
        if any(kw in line.lower() for kw in ['pledge', 'collateral', 'margin', 'haircut', 'utilised']):
            match = re.search(r'(-?\d+(?:\.\d+)?)', line)
            if match:
                amount = float(match.group(1))
                pledges.append({
                    'Date': trade_date,
                    'Broker': broker,
                    'Amount': abs(amount),
                    'Description': line[:100]
                })
    
    return pledges

def extract_account_summary(text, trade_date, broker, filename):
    """Extract account-level summary"""
    summary = {
        'Date': trade_date,
        'Broker': broker,
        'Filename': filename,
        'Total_Trades': 0,
        'Total_Fees': 0.0,
        'Settlement_Amount': 0.0,
        'Email_Processed': True
    }
    
    # Count trades
    trade_count = len(re.findall(r'^(NSE|BSE)', text, re.MULTILINE))
    summary['Total_Trades'] = trade_count
    
    # Extract total fees/brokerage
    brokerage_lines = re.findall(r'Brokerage.*?(-?\d+\.\d+)', text)
    if brokerage_lines:
        summary['Total_Fees'] = sum(float(x) for x in brokerage_lines)
    
    # Extract settlement amount
    settlement = re.search(r'Net Amount (?:Receivable|Payable).*?(-?\d+\.\d+)', text)
    if settlement:
        summary['Settlement_Amount'] = float(settlement.group(1))
    
    return summary

def parse_new_pdfs(pdf_files):
    """Parse newly downloaded PDFs and extract all data"""
    if not pdf_files:
        print("\nNo new PDFs to parse")
        # But still process existing PDFs if no new ones
        pdf_files = [f for f in os.listdir(pdf_folder) if f.endswith('.pdf') and 'contract' in f.lower()]
        if not pdf_files:
            return
        print(f"Processing {len(pdf_files)} existing PDFs...")
    
    print("\nParsing PDFs...")
    new_trades = []
    all_funds = []
    all_pledges = []
    all_summaries = []
    
    for idx, pdf_path in enumerate(pdf_files):
        try:
            if not pdf_path.endswith('.pdf'):
                pdf_path = os.path.join(pdf_folder, pdf_path)
            
            if not os.path.exists(pdf_path):
                continue
                
            text = extract_text_from_pdf(pdf_path)
            trade_date = extract_trade_date(text)
            filename = os.path.basename(pdf_path)
            
            # Determine broker
            broker = "Unknown"
            if "groww" in filename.lower():
                broker = "Groww"
            elif "mstock" in filename.lower() or "comm_contract" in filename.lower():
                broker = "mStock"
            elif "exness" in filename.lower():
                broker = "Exness"
            
            if trade_date:
                # Extract trades
                trades = parse_trades(text, trade_date, broker)
                new_trades.extend(trades)
                print(f"  OK {idx+1}. {filename}: {len(trades)} trades")
                
                # Extract funds
                funds = extract_funds_data(text, trade_date, broker)
                all_funds.extend(funds)
                if funds:
                    print(f"      → {len(funds)} fund transactions")
                
                # Extract pledges
                pledges = extract_pledges_data(text, trade_date, broker)
                all_pledges.extend(pledges)
                if pledges:
                    print(f"      → {len(pledges)} pledge records")
                
                # Extract summary
                summary = extract_account_summary(text, trade_date, broker, filename)
                all_summaries.append(summary)
                
            else:
                print(f"  SKIP {idx+1}. {filename}: Could not extract date")
        except Exception as e:
            print(f"  ERROR {idx+1}. Error: {str(e)[:60]}")
    
    # Save trades
    if new_trades:
        if os.path.exists(trades_csv):
            df_existing = pd.read_csv(trades_csv)
            df_new = pd.DataFrame(new_trades)
            df = pd.concat([df_existing, df_new], ignore_index=True)
            df = df.drop_duplicates(subset=['Date', 'Underlying', 'Strike', 'Type', 'Buy/Sell', 'Quantity'], keep='first')
        else:
            df = pd.DataFrame(new_trades)
        df.to_csv(trades_csv, index=False)
        print(f"\nOK trades.csv: {len(df)} trades")
    
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
        print(f"OK funds_transactions.csv: {len(df)} transactions")
    else:
        print("SKIP No fund transaction data found in PDFs")
    
    # Save pledges (even if empty)
    if all_pledges:
        if os.path.exists(pledges_csv):
            df_existing = pd.read_csv(pledges_csv)
            df_new = pd.DataFrame(all_pledges)
            df = pd.concat([df_existing, df_new], ignore_index=True)
        else:
            df = pd.DataFrame(all_pledges)
        df.to_csv(pledges_csv, index=False)
        print(f"OK pledges.csv: {len(df)} pledge records")
    else:
        # Create empty pledges CSV with headers for consistency
        pd.DataFrame(columns=['Date', 'Broker', 'Amount', 'Description']).to_csv(pledges_csv, index=False)
        print("SKIP No pledge data found (created empty file)")
    
    # Save account summary
    if all_summaries:
        if os.path.exists(account_summary_csv):
            df_existing = pd.read_csv(account_summary_csv)
            df_new = pd.DataFrame(all_summaries)
            df = pd.concat([df_existing, df_new], ignore_index=True)
        else:
            df = pd.DataFrame(all_summaries)
        df.to_csv(account_summary_csv, index=False)
        print(f"OK account_summary.csv: {len(df)} summaries")

# ===== MAIN =====
if __name__ == "__main__":
    print("=" * 50)
    print("TRADING JOURNAL - Gmail PDF Fetcher & Parser")
    print("=" * 50)
    
    # Download PDFs from Gmail
    downloaded_pdfs = download_pdfs_from_gmail()
    
    # Parse and add to trades.csv
    parse_new_pdfs(downloaded_pdfs)
    
    print("\n" + "=" * 50)
    print("All tasks complete!")
    print("=" * 50)
