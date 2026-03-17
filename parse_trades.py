import pdfplumber
import pandas as pd
import os
import re
from datetime import datetime

def extract_text_from_pdf(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        text = ""
        for page in pdf.pages:
            text += page.extract_text() + "\n"
    return text

def parse_trades(text, trade_date):
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
                    'Net Total': net_total
                }
                trades.append(trade)
        if 'Future &' in line and 'Options' in line:  # End of section
            in_trades_section = False
    return trades

def extract_trade_date(text):
    match = re.search(r'Trade Date (\d{2}-\d{2}-\d{4})', text)
    if match:
        return datetime.strptime(match.group(1), '%d-%m-%Y').date()
    return None

def process_all_pdfs(directory):
    all_trades = []
    for file in os.listdir(directory):
        if file.endswith('.pdf') and 'Contract_Note' in file:
            pdf_path = os.path.join(directory, file)
            text = extract_text_from_pdf(pdf_path)
            trade_date = extract_trade_date(text)
            if trade_date:
                trades = parse_trades(text, trade_date)
                all_trades.extend(trades)
    df = pd.DataFrame(all_trades)
    df.to_csv('trades.csv', index=False)
    return df

if __name__ == "__main__":
    directory = '.'
    df = process_all_pdfs(directory)
    print(f"Extracted {len(df)} trades")
    print(df.head())