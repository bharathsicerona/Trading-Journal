import sys
import os
import logging
from pdf_parser import extract_text_from_pdf
from dotenv import load_dotenv

try:
    import config
except ImportError:
    config = None

load_dotenv()

logger = logging.getLogger(__name__)

def debug_pdf(pdf_path):
    if not os.path.exists(pdf_path):
        logger.error(f"File not found: {pdf_path}")
        return
        
    password = os.getenv("BROKER_PDF_PASSWORD")
    if not password and config and hasattr(config, 'BROKER_PDF_PASSWORD'):
        password = config.BROKER_PDF_PASSWORD

    logger.info(f"Extracting text from {pdf_path} (Password: {'Provided' if password else 'None'})")
    
    text = extract_text_from_pdf(pdf_path, password=password)
    
    # Save the decrypted raw text to a .txt file for easy inspection
    out_path = pdf_path + ".txt"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(text)
        
    logger.info(f"Successfully extracted {len(text)} characters.")
    logger.info(f"✅ Full text saved to: {out_path}")
    
    print("\n--- FIRST 1000 CHARACTERS ---")
    print(text[:1000])
    print("-----------------------------\n")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
    
    # You can pass a specific PDF filename via terminal, or it defaults to a common mStock file
    target_pdf = sys.argv[1] if len(sys.argv) > 1 else os.path.join("pdfs", "COMM_CONTRACT_20260317_MA1749301_8580696.pdf")
    
    debug_pdf(target_pdf)
