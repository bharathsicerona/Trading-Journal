import pdfplumber
import re

# Test with a contract note PDF to debug extraction
pdf_file = "Contract_Note_4810259443_16-Mar-2026.pdf"

with pdfplumber.open(pdf_file) as pdf:
    text = ""
    for page in pdf.pages:
        text += page.extract_text() + "\n"

# Print sections that contain "Pay"
print("=== SEARCHING FOR PAY SECTIONS ===")
lines = text.split('\n')
for i, line in enumerate(lines):
    if 'pay' in line.lower() or 'pledge' in line.lower() or 'margin' in line.lower():
        print(f"Line {i}: {line[:100]}")

print("\n=== FULL SETTLEMENT SECTION ===")
# Find and print settlement section
in_settlement = False
for line in lines:
    if 'Settlement' in line or 'Net Amount' in line:
        in_settlement = True
    if in_settlement:
        print(line)
        if 'Future & Options' in line and 'Settlement' not in line:
            break
