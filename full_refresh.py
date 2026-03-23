import os
import glob
import logging
import time
import re
from datetime import datetime
import pandas as pd
from fetch_and_parse_gmail import download_pdfs_from_gmail, parse_new_pdfs, pdf_folder, trading_dir

logger = logging.getLogger(__name__)

YEAR_PATTERN = re.compile(r'(20\d{2})')


def _file_belongs_to_year(filename: str, target_year: int) -> bool:
    match = YEAR_PATTERN.search(filename)
    return bool(match and int(match.group(1)) == target_year)


def _prune_csv_for_year(csv_path: str, target_year: int) -> None:
    if not os.path.exists(csv_path):
        return

    df = pd.read_csv(csv_path)
    if df.empty:
        return

    original_len = len(df)

    if 'Filename' in df.columns:
        mask = df['Filename'].astype(str).apply(lambda name: _file_belongs_to_year(name, target_year))
        df = df.loc[~mask].copy()
    elif 'Date' in df.columns:
        dates = pd.to_datetime(df['Date'], errors='coerce')
        df = df.loc[dates.dt.year != target_year].copy()
    else:
        return

    if len(df) != original_len:
        df.to_csv(csv_path, index=False)
        logger.info(f"Pruned {original_len - len(df)} rows from {os.path.basename(csv_path)} for year {target_year}")


def perform_full_refresh(year=None):
    target_year = year if year else datetime.now().year
    logger.info(f"Starting refresh for {target_year}: removing only that year's data before re-downloading...")

    # 1. Prune CSV data files for the requested year only.
    csv_files = [
        "trades.csv",
        "funds_transactions.csv",
        "pledges.csv",
        "account_summary.csv",
        "processed_files.csv"
    ]

    for csv_file in csv_files:
        file_path = os.path.join(trading_dir, csv_file)
        _prune_csv_for_year(file_path, target_year)

    # 2. Delete only PDFs for the requested year.
    if os.path.exists(pdf_folder):
        pdf_files = glob.glob(os.path.join(pdf_folder, "*.pdf"))
        deleted_count = 0
        for pdf_file in pdf_files:
            try:
                if _file_belongs_to_year(os.path.basename(pdf_file), target_year):
                    os.remove(pdf_file)
                    deleted_count += 1
            except Exception as e:
                logger.warning(f"Could not delete {pdf_file}: {e}")
        logger.info(f"Deleted {deleted_count} PDFs from '{pdf_folder}' for year {target_year}")

    logger.info("Cleanup complete. Starting fresh download from Gmail...")
    time.sleep(2)  # Short pause before starting

    # 3. Fetch the requested year's PDFs.
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
    print("WARNING: YEAR-SCOPED DATA REFRESH")
    print("="*60)
    print(f"This will remove parsed CSV rows and PDFs for {current_year} only.")
    print(f"It will then re-download your trading history for {current_year}.")

    perform_full_refresh(year=current_year)
