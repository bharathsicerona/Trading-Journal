# Trading Journal Dashboard Setup Guide

This guide explains how to set up the project safely, run it manually, and automate it on Windows.

## 1. Prerequisites

You need:

- Python 3.10 or later
- A Gmail account with 2-factor authentication enabled
- A Gmail App Password
- Windows Task Scheduler if you want daily automation

## 2. Create The Python Environment

```powershell
cd C:\Users\bhara\OneDrive\Documents\Trading_Automation
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install the main dependencies:

```powershell
.\task.bat install
```

Optional:

```powershell
pip install streamlit-plotly-events
```

## 3. Configure Gmail Access

### Step 1: Enable 2FA

Enable two-factor authentication on your Gmail account.

### Step 2: Create an App Password

1. Go to [Google App Passwords](https://myaccount.google.com/apppasswords)
2. Create an app password for Mail
3. Copy the generated 16-character password

### Step 3: Create `.env`

Create a `.env` file in the project root:

```env
EMAIL_ACCOUNT=your-email@gmail.com
APP_PASSWORD=your-16-character-app-password
BROKER_PDF_PASSWORD=
```

Fastest option:

```powershell
Copy-Item .env.example .env
```

Meaning:

- `EMAIL_ACCOUNT`: required Gmail login
- `APP_PASSWORD`: required Gmail app password
- `BROKER_PDF_PASSWORD`: optional PDF password for protected broker files

Important:

- Do not store secrets in `config.py`
- Do not commit `.env`
- If credentials are exposed, revoke and replace them

## 4. First Manual Run

Validate the local environment first:

```powershell
.\task.bat validate
```

Run the Gmail sync and parser:

```powershell
.\task.bat sync
```

This will:

1. Connect to Gmail
2. Download matching PDF attachments
3. Save them in `pdfs/`
4. Update `processed_files.csv`
5. Parse data into the CSV outputs

Expected output files:

- `trades.csv`
- `funds_transactions.csv`
- `pledges.csv`
- `account_summary.csv`
- `processed_files.csv`

## 5. Launch The Dashboard

```powershell
.\task.bat dashboard
```

Dashboard areas:

- Trades
- Funds Flow
- Pledges
- Summary
- Analytics
- Risk Analysis

## 6. Working With Existing PDFs

If you already have PDFs in `pdfs/`, you can parse them without downloading again:

```powershell
.\task.bat parse
```

If older PDFs are missing broker prefixes, tag them with:

```powershell
.\.venv\Scripts\python.exe tag_existing_pdfs.py
```

## 7. Year-Scoped Refresh

Use `full_refresh.py` when you want to rebuild one year's data from Gmail.

```powershell
.\task.bat refresh
```

Specific year:

```powershell
.\task.bat refresh 2026
```

Current behavior:

- Removes only the requested year's rows from CSV files
- Removes only that year's PDFs from `pdfs/`
- Re-downloads that same year from Gmail

This is intentionally safer than a full-history wipe.

## 8. Task Scheduler Automation

There are two automation paths in this repo.

### Option A: `setup_scheduler.ps1`

Recommended if you want the more detailed logging path.

Behavior:

- Creates task: `Trading Automation - Daily Update`
- Runs weekdays at `8:00 AM`
- Executes `run_trading_automation.bat`
- Writes logs to `logs/trading_automation.log`

Setup:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
.\setup_scheduler.ps1
```

### Option B: `setup_daily_scheduler.ps1`

Simpler daily setup.

Behavior:

- Creates task: `Trading Automation Daily`
- Runs weekdays at `9:00 AM`
- Executes `daily_update.bat`
- Writes logs to `logs/daily_update.log`

Setup:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
.\setup_daily_scheduler.ps1
```

Both scripts should be run from an elevated PowerShell window.

## 9. Logs And Debugging

Primary logs:

- `logs/trading_automation.log`
- `logs/daily_update.log`

Useful debug helpers:

- `tasks.ps1` and `task.bat`: a Makefile-style task runner for common project actions
- `validate_setup.py`: checks that the machine is ready to run the project
- `cleanup_data.py`: removes duplicates from generated CSV files using the current dedupe rules
- `debug_pdf.py`: extracts full text from a target PDF and saves a `.txt` copy next to it
- `extract_pdf.py`: prints extracted text for a selected PDF
- `check_comm.py`: quick contract-note extraction check

Example:

```powershell
.\.venv\Scripts\python.exe debug_pdf.py "pdfs\Groww__some_file.pdf"
```

## 10. Testing

Run tests with:

```powershell
python -m unittest discover -v
```

If you get import errors, make sure you installed the dependencies into the interpreter you are using.

## 11. Data Quality Notes

Recent fixes added deduplication for:

- `processed_files.csv` by `Filename`
- `account_summary.csv` by `Filename`
- `pledges.csv` by `Date`, `Broker`, `Amount`, `Description`

The dashboard's round-trip grouping now includes `Expiry`, so positions with the same strike and type but different expiries are no longer merged together.

You can re-run the cleanup tool manually with:

```powershell
.\task.bat cleanup
```

## 12. Troubleshooting

### Gmail login fails

- Confirm 2FA is enabled
- Confirm you are using an App Password, not your regular Gmail password
- Confirm `.env` contains `EMAIL_ACCOUNT` and `APP_PASSWORD`

### No new data appears

- Check the sender list in `config.py`
- Check the logs in `logs/`
- Verify the emails really contain PDF attachments
- Remember that some data may come from statement PDFs, not just contract notes

### Dashboard shows no records

- Confirm the CSV files exist in the project root
- Run `fetch_and_parse_gmail.py` manually first
- Check for parser errors in the logs

### Tests fail with missing modules

- Activate `.venv`
- Reinstall dependencies
- Run the tests again from the same environment

## 13. Task Runner Quick Reference

The project includes a small Windows task runner so you can use named tasks instead of long commands.

Examples:

```powershell
.\task.bat help
.\task.bat install
.\task.bat validate
.\task.bat sync
.\task.bat parse
.\task.bat cleanup
.\task.bat dashboard
.\task.bat refresh 2026
.\task.bat test
```
