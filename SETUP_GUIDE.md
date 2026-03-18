# Trading Journal Dashboard - Setup & Automation Guide

## Quick Start

### 1. Initial Setup

```powershell
# Configure Python environment
python -m venv .venv
.venv\Scripts\Activate.ps1

# Install dependencies
pip install pdfplumber pandas streamlit plotly gspread oauth2client imaplib
```

### 2. Configure Gmail Access

Before running the automation scripts, you need to:

1. **Enable 2-Factor Authentication** on your Gmail account
2. **Generate an App Password**:
   - Go to [https://myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
   - Select "Mail" and "Windows Computer"
   - Copy the 16-digit password

3. **Update** `fetch_and_parse_gmail.py`:
   - Replace `your_email@gmail.com` with your Gmail address
   - Replace `your_16_digit_app_password` with the password from step 2

### 3. Schedule Daily Automation

**Option A: Automatic Setup (Recommended)**

1. Open PowerShell as **Administrator**
2. Navigate to the Trading_Automation folder
3. Run:
   ```powershell
   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
   .\setup_scheduler.ps1
   ```

This creates a scheduled task that runs every working day (Mon-Fri) at 8:00 AM.

**Option B: Manual Setup**

1. Open **Task Scheduler** (Windows key + `taskschd.msc`)
2. Click "Create Basic Task"
3. Name: `Trading Automation - Daily Update`
4. Trigger: Daily on working days at 8:00 AM
5. Action: Start a program
   - Program: `C:\Users\bhara\OneDrive\Documents\Trading_Automation\run_trading_automation.bat`
6. Click Finish

### 4. Run on Demand

```powershell
# Fetch and parse PDFs
.\.venv\Scripts\python.exe fetch_and_parse_gmail.py

# Launch dashboard
.\.venv\Scripts\python.exe -m streamlit run dashboard.py
```

## File Structure

```
Trading_Automation/
├── fetch_and_parse_gmail.py    # Gmail PDF downloader & parser
├── parse_trades.py              # Initial PDF parser (for local PDFs)
├── dashboard.py                 # Streamlit dashboard
├── run_trading_automation.bat   # Scheduled task runner
├── setup_scheduler.ps1          # Task Scheduler setup script
│
├── trades.csv                   # Extracted trade data
├── funds_transactions.csv       # Deposits/withdrawals
├── pledges.csv                  # Pledge/collateral data
├── account_summary.csv          # Account summaries
│
├── pdfs/                        # All downloaded PDFs
│   ├── Contract_Note_*.pdf      # Groww contract notes
│   ├── COMM_CONTRACT_*.pdf      # mStock contract notes
│   └── *.pdf                    # Other broker PDFs
│
└── logs/
    └── trading_automation.log   # Execution logs
```

## What Gets Extracted

### Trades
- Date, Exchange, Underlying, Strike, Type, Expiry
- Buy/Sell, Quantity, WAP, Brokerage, Net Price, Net Total

### Funds
- Date, Broker, Type (Deposit/Withdrawal/Settlement)
- Amount, Description

### Pledges
- Date, Broker, Amount, Description

### Summary
- Date, Broker, Total Trades, Total Fees, Settlement Amount

## Dashboard Tabs

1. **📈 Trades** - Daily P&L, cumulative returns, win rate
2. **💰 Funds Flow** - Deposits, withdrawals, net cash flow
3. **📌 Pledges** - Pledge usage and trends
4. **📋 Summary** - Per-PDF overview and statistics
5. **📊 Analytics** - ROI, profit factor, trading performance metrics

## Troubleshooting

**Task not running?**
- Check logs in `logs\trading_automation.log`
- Ensure Gmail credentials are correct
- Verify 2FA and App Password are set up

**No data showing?**
- Run `fetch_and_parse_gmail.py` manually to debug
- Check that PDFs have "Contract_Note" in the filename

**Dashboard not loading?**
- Ensure `trades.csv` exists
- Run `streamlit run dashboard.py` with the `.venv` activated

## Auto-Run the Dashboard on Startup (Optional)

To launch the dashboard automatically on startup:

1. Create a shortcut to:
   ```
   C:\Users\bhara\OneDrive\Documents\Trading_Automation\.venv\Scripts\streamlit.exe run dashboard.py
   ```
2. Place it in `C:\Users\bhara\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup`

---

**Questions?** Check the logs or review the individual scripts for detailed operation.
