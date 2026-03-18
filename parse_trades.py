import os
import re
import logging
from datetime import datetime
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

try:
    import config
except ImportError:
    config = None

# Reuse pdf parsing helpers
from pdf_parser import (
    extract_text_from_pdf, parse_trades as robust_parse_trades, extract_trade_date
)

logger = logging.getLogger(__name__)


def process_all_pdfs(directory: str) -> pd.DataFrame:
    """Process all contract PDFs in a directory and write trades.csv"""
    all_trades = []
    processed_files = set()
    for file in os.listdir(directory):
        lower_file = file.lower()
        if file.endswith('.pdf') and ('contract_note' in lower_file or 'comm_contract' in lower_file):
            base_file = re.sub(r'_\d{10,}\.pdf$', '.pdf', file)
            if base_file in processed_files:
                logger.info(f"Skipping duplicate file: {file}")
                continue
            processed_files.add(base_file)

            pdf_path = os.path.join(directory, file)
            try:
                base_filename = file.split('__')[-1] if '__' in file else file
                if '__' in file:
                    broker = file.split('__')[0].replace('_', ' ')
                else:
                    broker = "Unknown"
                    if "mstock" in base_filename.lower() or "comm_contract" in base_filename.lower():
                        broker = "mStock"
                    elif "groww" in base_filename.lower() or "contract_note" in base_filename.lower() or "contract note" in base_filename.lower():
                        broker = "Groww"

                pdf_password = None
                if broker in ["Groww", "mStock"]:
                    pdf_password = os.getenv("BROKER_PDF_PASSWORD")
                    if not pdf_password and config and hasattr(config, 'BROKER_PDF_PASSWORD'):
                        pdf_password = config.BROKER_PDF_PASSWORD
                
                text = extract_text_from_pdf(pdf_path, password=pdf_password)
                trade_date = extract_trade_date(text)
                if trade_date:
                    trades = robust_parse_trades(text, trade_date, broker=broker)
                    all_trades.extend(trades)
                else:
                    logger.warning(f"Could not extract date from {file}")
            except Exception as e:
                logger.exception(f"Error processing {file}: {str(e)}")

    df = pd.DataFrame(all_trades)
    df.to_csv('trades.csv', index=False)
    return df


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
    directory = 'pdfs' if os.path.exists('pdfs') else '.'
    df = process_all_pdfs(directory)
    logger.info(f"Extracted {len(df)} trades")
    logger.info("\n" + str(df.head()))
