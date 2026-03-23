# Trading Journal Dashboard

This project downloads trading PDFs from Gmail, parses broker statements into CSV datasets, and presents the results in a Streamlit dashboard.

It is designed around a simple pipeline:

1. Download PDFs from Gmail
2. Detect the broker and tag filenames
3. Parse trades, funds, pledges, and account summaries
4. Save normalized CSV files
5. Explore everything in the dashboard

## What The Project Does

The project currently supports these main use cases:

- Download contract notes and statement PDFs from Gmail
- Parse Groww, mStock, and some Exness-style layouts
- Build these datasets:
  - `trades.csv`
  - `funds_transactions.csv`
  - `pledges.csv`
  - `account_summary.csv`
  - `processed_files.csv`
- Show analytics in `dashboard.py`
- Support scheduled daily refresh on Windows Task Scheduler

## Repository Structure

Core files:

- `fetch_and_parse_gmail.py`: Gmail download and incremental parsing pipeline
- `pdf_parser.py`: PDF text extraction and broker-specific parsing logic
- `parse_trades.py`: Local bulk PDF parser for existing files
- `dashboard.py`: Streamlit dashboard
- `full_refresh.py`: Year-scoped refresh for rebuilding one year's data
- `tag_existing_pdfs.py`: Adds broker prefixes to existing PDFs and updates `processed_files.csv`

Support files:

- `.env.example`: safe template for local environment variables
- `requirements.txt`: Python dependencies for the project
- `tasks.ps1`: PowerShell task runner for common project commands
- `task.bat`: simple Windows wrapper for the task runner
- `run_trading_automation.bat`: Runs the Gmail sync and logs to `logs/trading_automation.log`
- `daily_update.bat`: Simpler daily update runner with `logs/daily_update.log`
- `setup_scheduler.ps1`: Creates an 8:00 AM weekday task for `run_trading_automation.bat`
- `setup_daily_scheduler.ps1`: Creates a 9:00 AM weekday task for `daily_update.bat`
- `validate_setup.py`: checks Python version, required packages, environment variables, and expected files
- `cleanup_data.py`: deduplicates the generated CSV files using the project's current rules
- `debug_pdf.py`, `extract_pdf.py`, `check_comm.py`: PDF inspection helpers
- `test_pdf_parser.py`, `test_config.py`: Unit tests

Data folders:

- `pdfs/`: Downloaded and tagged PDFs
- `logs/`: Task and refresh logs

## Security

Gmail credentials must not be hardcoded in the source code.

The application now expects these environment variables to be present through a local `.env` file or your shell environment:

```env
EMAIL_ACCOUNT=your-email@gmail.com
APP_PASSWORD=your-16-character-app-password
BROKER_PDF_PASSWORD=optional-pdf-password
```

Notes:

- `EMAIL_ACCOUNT` and `APP_PASSWORD` are required for Gmail sync
- `BROKER_PDF_PASSWORD` is optional and only needed for password-protected PDFs
- Keep `.env` private and out of version control
- If credentials were ever exposed, revoke and replace them immediately

## Setup

### 1. Create a virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2. Install dependencies

```powershell
.\task.bat install
```

Optional packages:

- `streamlit-plotly-events` for click-based chart drilldowns

### 3. Create `.env`

Create a `.env` file in the project root with:

```env
EMAIL_ACCOUNT=your-email@gmail.com
APP_PASSWORD=your-16-character-app-password
BROKER_PDF_PASSWORD=
```

Quick start:

```powershell
Copy-Item .env.example .env
```

### 4. Run the parser pipeline

Validate the local setup before the first run:

```powershell
.\task.bat validate
```

Incremental Gmail sync:

```powershell
.\task.bat sync
```

Parse local PDFs already present in `pdfs/`:

```powershell
.\task.bat parse
```

### 5. Launch the dashboard

```powershell
.\task.bat dashboard
```

## Generated Files

### `trades.csv`

Contains parsed trades with fields such as:

- `Date`
- `Exchange`
- `Underlying`
- `Strike`
- `Type`
- `Expiry`
- `Buy/Sell`
- `Quantity`
- `WAP`
- `Brokerage`
- `Net Price`
- `Net Total`
- `Broker`

### `funds_transactions.csv`

Contains extracted deposits, withdrawals, and settlement amounts.

### `pledges.csv`

Contains pledge, collateral, and margin-related entries.

### `account_summary.csv`

Contains one summary row per processed PDF. The pipeline now deduplicates by filename to prevent double-counting on reprocessing.

### `processed_files.csv`

Tracks downloaded and tagged PDFs. The pipeline now deduplicates this file by filename.

## Dashboard Overview

`dashboard.py` contains six main tabs:

- `Trades`: P&L, cumulative returns, broker and underlying breakdowns
- `Funds Flow`: deposits, withdrawals, settlement analysis
- `Pledges`: collateral and margin-related records
- `Summary`: per-PDF trade count, fees, settlement summaries
- `Analytics`: win rate, profit factor, expectancy, time-based analysis
- `Risk Analysis`: drawdown, VaR, CVaR, Sharpe, Kelly-style sizing, stress checks

Important dashboard behavior:

- Global filters apply across the views
- Round-trip grouping now includes `Expiry`, so different expiries on the same day are not merged together
- `processed_files.csv` is shown in the sidebar when available

## Gmail Download Behavior

`fetch_and_parse_gmail.py`:

- Reads senders from `config.py`
- Downloads matching PDF attachments
- Tags files with a broker prefix like `Groww__...pdf`
- Avoids overwriting an existing file by appending a timestamp
- Logs processed metadata to `processed_files.csv`
- Parses trades, funds, pledges, and summaries into CSVs

When no new PDFs are downloaded, the parser rescans all existing PDFs in `pdfs/`, not just contract notes. This ensures statement PDFs can still contribute funds, pledge, and summary data.

## Refresh And Rebuild Behavior

`full_refresh.py` is now year-scoped.

That means:

- It removes only the requested year's rows from the CSV files
- It removes only PDFs whose filenames belong to that year
- It then re-downloads and rebuilds that same year

This avoids deleting older history by accident.

Run it with:

```powershell
.\task.bat refresh
```

Specific year:

```powershell
.\task.bat refresh 2026
```

## Windows Automation

There are two scheduler setups in the repo.

### Option 1: `setup_scheduler.ps1`

- Runs `run_trading_automation.bat`
- Schedules weekdays at `8:00 AM`
- Logs to `logs/trading_automation.log`

### Option 2: `setup_daily_scheduler.ps1`

- Runs `daily_update.bat`
- Schedules weekdays at `9:00 AM`
- Logs to `logs/daily_update.log`

Run either PowerShell setup script as Administrator.

## Testing

Run all tests:

```powershell
python -m unittest discover -v
```

Run specific files:

```powershell
python -m unittest test_pdf_parser.py -v
python -m unittest test_config.py -v
```

If tests fail to import modules, install the dependencies into the same Python interpreter you are using to run the tests.

## Maintenance Notes

- Existing duplicate rows in `processed_files.csv` and `account_summary.csv` should be cleaned if they were generated before the dedupe fixes
- `tag_existing_pdfs.py` can be used to normalize older PDFs with broker prefixes
- `debug_pdf.py` is helpful when a broker layout changes and you need the extracted raw text
- `cleanup_data.py` can be run at any time to deduplicate the generated CSV files safely

## Common Commands

```powershell
# Activate venv
.\.venv\Scripts\Activate.ps1

# Show task runner help
.\task.bat help

# Validate local setup
.\task.bat validate

# Install dependencies
.\task.bat install

# Gmail sync and parse
.\task.bat sync

# Parse local PDFs
.\task.bat parse

# Deduplicate generated CSV files
.\task.bat cleanup

# Launch dashboard
.\task.bat dashboard

# Year-scoped rebuild
.\task.bat refresh

# Year-scoped rebuild for a specific year
.\task.bat refresh 2026

# Run tests
.\task.bat test
```
