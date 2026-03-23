import importlib
import os
import sys

import config


REQUIRED_PACKAGES = [
    "pdfplumber",
    "pandas",
    "streamlit",
    "plotly",
    "numpy",
    "dotenv",
]


def check_python() -> bool:
    ok = sys.version_info >= (3, 10)
    status = "OK" if ok else "FAIL"
    print(f"[{status}] Python version: {sys.version.split()[0]}")
    return ok


def check_packages() -> bool:
    all_ok = True
    for package in REQUIRED_PACKAGES:
        try:
            importlib.import_module(package)
            print(f"[OK] Package available: {package}")
        except Exception:
            print(f"[FAIL] Missing package: {package}")
            all_ok = False
    return all_ok


def check_env() -> bool:
    missing = config.get_missing_required_env_vars()
    if missing:
        print(f"[FAIL] Missing required environment variables: {', '.join(missing)}")
        if not os.path.exists(".env"):
            print("[INFO] No .env file found in the project root.")
        else:
            print("[INFO] .env file exists, but one or more required values are empty.")
        return False

    print("[OK] Required Gmail environment variables are configured.")
    if config.BROKER_PDF_PASSWORD:
        print("[OK] BROKER_PDF_PASSWORD is configured.")
    else:
        print("[INFO] BROKER_PDF_PASSWORD is not set. This is fine unless your PDFs are password-protected.")
    return True


def check_paths() -> bool:
    all_ok = True
    for path in ["pdfs", "logs"]:
        if os.path.exists(path):
            print(f"[OK] Path exists: {path}")
        else:
            print(f"[INFO] Path will be created when needed: {path}")
    for path in ["fetch_and_parse_gmail.py", "dashboard.py", "pdf_parser.py"]:
        if os.path.exists(path):
            print(f"[OK] File exists: {path}")
        else:
            print(f"[FAIL] Missing expected file: {path}")
            all_ok = False
    return all_ok


if __name__ == "__main__":
    print("Trading Journal setup validation")
    print("=" * 32)

    checks = [
        check_python(),
        check_packages(),
        check_env(),
        check_paths(),
    ]

    if all(checks):
        print("\nSetup looks good.")
        raise SystemExit(0)

    print("\nSetup validation found issues. Fix the FAILED items above and run again.")
    raise SystemExit(1)
