param(
    [Parameter(Position = 0)]
    [string]$Task = "help",

    [Parameter(Position = 1)]
    [string]$Arg1 = ""
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$RequirementsFile = Join-Path $ProjectRoot "requirements.txt"

function Write-TaskHelp {
    Write-Host "Trading Journal task runner"
    Write-Host ""
    Write-Host "Usage:"
    Write-Host "  .\task.bat <task> [arg]"
    Write-Host "  powershell -ExecutionPolicy Bypass -File .\tasks.ps1 <task> [arg]"
    Write-Host ""
    Write-Host "Tasks:"
    Write-Host "  help            Show this help"
    Write-Host "  install         Install Python dependencies from requirements.txt"
    Write-Host "  validate        Validate local setup"
    Write-Host "  sync            Download Gmail PDFs and parse outputs"
    Write-Host "  parse           Parse local PDFs already present in pdfs\"
    Write-Host "  cleanup         Deduplicate generated CSV files"
    Write-Host "  dashboard       Launch the Streamlit dashboard"
    Write-Host "  refresh [year]  Rebuild one year of data using full_refresh.py"
    Write-Host "  test            Run the full unittest suite"
    Write-Host "  test-config     Run config tests only"
    Write-Host "  test-parser     Run PDF parser tests only"
}

function Assert-VenvPython {
    if (-not (Test-Path $VenvPython)) {
        throw "Virtual environment Python not found at '$VenvPython'. Create the venv first with: python -m venv .venv"
    }
}

function Invoke-VenvPython {
    param(
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$PythonArgs
    )

    Assert-VenvPython
    Push-Location $ProjectRoot
    try {
        & $VenvPython @PythonArgs
        if ($LASTEXITCODE -ne 0) {
            exit $LASTEXITCODE
        }
    }
    finally {
        Pop-Location
    }
}

switch ($Task.ToLowerInvariant()) {
    "help" {
        Write-TaskHelp
    }
    "install" {
        Assert-VenvPython
        if (-not (Test-Path $RequirementsFile)) {
            throw "requirements.txt not found at '$RequirementsFile'"
        }
        Invoke-VenvPython -PythonArgs @("-m", "pip", "install", "-r", $RequirementsFile)
    }
    "validate" {
        Invoke-VenvPython -PythonArgs @("validate_setup.py")
    }
    "sync" {
        Invoke-VenvPython -PythonArgs @("fetch_and_parse_gmail.py")
    }
    "parse" {
        Invoke-VenvPython -PythonArgs @("parse_trades.py")
    }
    "cleanup" {
        Invoke-VenvPython -PythonArgs @("cleanup_data.py")
    }
    "dashboard" {
        Invoke-VenvPython -PythonArgs @("-m", "streamlit", "run", "dashboard.py")
    }
    "refresh" {
        if ([string]::IsNullOrWhiteSpace($Arg1)) {
            Invoke-VenvPython -PythonArgs @("full_refresh.py")
        }
        else {
            Invoke-VenvPython -PythonArgs @("full_refresh.py", $Arg1)
        }
    }
    "test" {
        Invoke-VenvPython -PythonArgs @("-m", "unittest", "discover", "-v")
    }
    "test-config" {
        Invoke-VenvPython -PythonArgs @("-m", "unittest", "test_config.py", "-v")
    }
    "test-parser" {
        Invoke-VenvPython -PythonArgs @("-m", "unittest", "test_pdf_parser.py", "-v")
    }
    default {
        Write-Host "Unknown task: $Task" -ForegroundColor Red
        Write-Host ""
        Write-TaskHelp
        exit 1
    }
}
