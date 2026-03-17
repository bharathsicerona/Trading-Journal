import pdfplumber
import os

# Function to extract text from a PDF
def extract_text_from_pdf(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        text = ""
        for page in pdf.pages:
            text += page.extract_text()
    return text

# Test with one PDF
pdf_file = "Contract_Note_4810259443_16-Mar-2026.pdf"
if os.path.exists(pdf_file):
    text = extract_text_from_pdf(pdf_file)
    print(text)
else:
    print("PDF not found")