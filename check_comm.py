import os
import logging
import sys
from pdf_parser import extract_text_from_pdf

logger = logging.getLogger(__name__)

pdf_file = sys.argv[1] if len(sys.argv) > 1 else "COMM_CONTRACT_20260101_MA1749301_6827764.pdf"

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
    if os.path.exists(pdf_file):
        text = extract_text_from_pdf(pdf_file)
        logger.info(text[:1000])  # First 1000 chars
    else:
        logger.error(f"PDF not found: {pdf_file}")
