import os
import pandas as pd


CSV_RULES = {
    "processed_files.csv": ["Filename"],
    "account_summary.csv": ["Filename"],
    "pledges.csv": ["Date", "Broker", "Amount", "Description"],
    "funds_transactions.csv": ["Date", "Broker", "Type", "Amount"],
    "trades.csv": ["Date", "Underlying", "Strike", "Type", "Buy/Sell", "Quantity", "WAP", "Net Total"],
}


def cleanup_csv(csv_name: str, subset: list[str]) -> None:
    if not os.path.exists(csv_name):
        print(f"[SKIP] {csv_name} not found")
        return

    df = pd.read_csv(csv_name)
    before = len(df)
    if before == 0:
        print(f"[SKIP] {csv_name} is empty")
        return

    available_subset = [column for column in subset if column in df.columns]
    if not available_subset:
        print(f"[SKIP] {csv_name} does not contain the expected dedupe columns")
        return

    cleaned = df.drop_duplicates(subset=available_subset, keep="first")
    removed = before - len(cleaned)
    cleaned.to_csv(csv_name, index=False)
    print(f"[OK] {csv_name}: removed {removed} duplicate rows, kept {len(cleaned)} rows")


if __name__ == "__main__":
    print("Cleaning CSV outputs")
    print("=" * 20)
    for csv_name, subset in CSV_RULES.items():
        cleanup_csv(csv_name, subset)
