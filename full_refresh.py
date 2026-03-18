import os
import glob
import logging
import time
from datetime import datetime
from fetch_and_parse_gmail import download_pdfs_from_gmail, parse_new_pdfs, pdf_folder, trading_dir

logger = logging.getLogger(__name__)

def perform_full_refresh(year=None):
    target_year = year if year else datetime.now().year
    logger.info("Starting Full Refresh: Deleting all existing data and re-downloading from Gmail...")
    
    # 1. Delete CSV data files
    csv_files = [
        "trades.csv",
        "funds_transactions.csv",
        "pledges.csv",
        "account_summary.csv",
        "processed_files.csv"
    ]
    
    for csv_file in csv_files:
        file_path = os.path.join(trading_dir, csv_file)
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"Deleted: {csv_file}")
            
    # 2. Delete all PDFs in the pdfs folder
    if os.path.exists(pdf_folder):
        pdf_files = glob.glob(os.path.join(pdf_folder, "*.pdf"))
        for pdf_file in pdf_files:
            try:
                os.remove(pdf_file)
            except Exception as e:
                logger.warning(f"Could not delete {pdf_file}: {e}")
        logger.info(f"Deleted {len(pdf_files)} PDFs from '{pdf_folder}'")
        
    logger.info("Cleanup complete. Starting fresh download from Gmail...")
    time.sleep(2)  # Short pause before starting
    
    # 3. Fetch full contract notes 
    # Grab up to 1000 emails per configured broker specifically for the target year
    since_date = f"01-Jan-{target_year}"
    before_date = f"01-Jan-{target_year + 1}"
    downloaded_pdfs = download_pdfs_from_gmail(since_date=since_date, before_date=before_date, max_emails=1000)
    
    # 4. Parse the newly downloaded PDFs
    if downloaded_pdfs:
        logger.info(f"Successfully downloaded {len(downloaded_pdfs)} PDFs. Beginning parsing...")
        parse_new_pdfs(downloaded_pdfs)
        logger.info("\n=== FULL REFRESH COMPLETED SUCCESSFULLY! ===")
    else:
        logger.warning("\nFull refresh finished, but no PDFs were found to download.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
    
    current_year = datetime.now().year
    print("="*60)
    print("WARNING: FULL DATA REFRESH")
    print("="*60)
    print("This will completely DELETE all parsed CSV files and downloaded PDFs.")
    print(f"It will then attempt to re-download your trading history for {current_year}.")
    
    perform_full_refresh(year=current_year)