# Trading Journal Dashboard

This project extracts trade data from PDF contract notes and displays it in an interactive dashboard.

## Security Notice ⚠️

**IMPORTANT:** Your Gmail credentials are stored in `config.py`. This file is automatically excluded from git commits via `.gitignore`. **Never commit `config.py` to version control** as it contains sensitive information.

### Git Setup (Do This First!)
Before initializing git, ensure your environment is secure:

```bash
# Initialize git repository
git init

# Check that config.py is ignored (should show nothing)
git status --porcelain config.py

# If you accidentally commit sensitive data:
git rm --cached config.py
git commit -m "Remove sensitive config file"
```

### If You Accidentally Commit Sensitive Data:
1. Revoke the Gmail app password immediately
2. Generate a new app password at https://myaccount.google.com/apppasswords
3. Update `config.py` with the new password
4. Remove from git history: `git filter-branch --tree-filter 'rm -f config.py' HEAD`

## Setup

1. Install dependencies: `pip install pdfplumber pandas streamlit plotly gspread oauth2client python-dotenv`

2. Configure credentials in `config.py`:
   ```python
   EMAIL_ACCOUNT = "your-email@gmail.com"
   APP_PASSWORD = "your-16-char-app-password"
   ```

3. Run the parser: `python parse_trades.py` to extract data from PDFs into `trades.csv`

4. Run the dashboard: `streamlit run dashboard.py`

## Testing

The project includes unit tests to ensure code reliability:

- Run all tests: `python -m unittest discover`
- Run specific test file: `python -m unittest test_pdf_parser.py`
- Run with verbose output: `python -m unittest discover -v`

Tests cover:
- PDF text extraction
- Trade data parsing
- Funds and pledges extraction
- Configuration loading
- Date parsing and validation

## Desktop Shortcuts
Two convenient ways to launch the dashboard:

**Option 1: Direct Python Shortcut** (Recommended)
- Desktop shortcut: "Trading Dashboard.lnk"
- Launches directly with Python virtual environment

**Option 2: Batch File Shortcut**
- Desktop shortcut: "Trading Dashboard (Batch).lnk"
- Uses batch file with virtual environment activation
- Alternative: Run `launch_dashboard.bat` directly
## Features

- Summary metrics: Total trades and P&L
- Daily and cumulative P&L charts
- Trades table
- Breakdown by underlying asset

## Automation

The project includes automated daily updates via Windows Task Scheduler:

- `daily_update.bat` - Batch file for scheduled execution
- `setup_daily_scheduler.ps1` - PowerShell script to configure Task Scheduler
- Runs every weekday at 9:00 AM
- Logs execution details to `logs/daily_update.log`

## Notes

- Currently processes PDFs with "Contract_Note" in filename
- Assumes NIFTY and SENSEX options format