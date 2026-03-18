import os
import logging
import sys
from pdf_parser import extract_text_from_pdf

logger = logging.getLogger(__name__)

# Test with one PDF
pdf_file = sys.argv[1] if len(sys.argv) > 1 else "Contract_Note_4810259443_16-Mar-2026.pdf"
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
    if os.path.exists(pdf_file):
        text = extract_text_from_pdf(pdf_file)
        logger.info(text)
    else:
        logger.error("PDF not found")
