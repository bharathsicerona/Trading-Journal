import pdfplumber

pdf_file = "COMM_CONTRACT_20260101_MA1749301_6827764.pdf"
with pdfplumber.open(pdf_file) as pdf:
    text = ""
    for page in pdf.pages:
        text += page.extract_text()
print(text[:1000])  # First 1000 chars