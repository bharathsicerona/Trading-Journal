import os
import time
import pandas as pd
from datetime import datetime

PDF_DIR = os.path.join(os.getcwd(), 'pdfs')
processed_csv = os.path.join(os.getcwd(), 'processed_files.csv')

def detect_broker(filename: str) -> str:
    fn = (filename or '').lower()
    if 'groww' in fn or 'contract_note' in fn or 'contract note' in fn:
        return 'Groww'
    if 'mstock' in fn or 'm-stock' in fn or 'comm_contract' in fn:
        return 'mStock'
    if 'exness' in fn:
        return 'Exness'
    return 'Unknown'

if __name__ == '__main__':
    if not os.path.exists(PDF_DIR):
        print('PDF directory not found:', PDF_DIR)
        raise SystemExit(1)

    rows = []
    updated = 0
    for fname in os.listdir(PDF_DIR):
        if not fname.lower().endswith('.pdf'):
            continue
        # if already tagged (contains __), skip renaming but ensure processed_files entry exists
        if '__' in fname:
            broker = fname.split('__', 1)[0]
            path = os.path.join(PDF_DIR, fname)
        else:
            broker = detect_broker(fname)
            name, ext = os.path.splitext(fname)
            new_name = f"{broker.replace(' ', '_')}__{name}{ext}"
            src = os.path.join(PDF_DIR, fname)
            dst = os.path.join(PDF_DIR, new_name)
            # avoid overwriting
            if os.path.exists(dst):
                dst = os.path.join(PDF_DIR, f"{broker.replace(' ', '_')}__{name}_{int(time.time())}{ext}")
            os.rename(src, dst)
            path = dst
            updated += 1
        rows.append({'Filename': os.path.basename(path), 'Broker': broker, 'Source': 'existing', 'DownloadedAt': datetime.now().isoformat(), 'SizeKB': round(os.path.getsize(path)/1024,1)})

    # write processed_files.csv
    if os.path.exists(processed_csv):
        try:
            dfp = pd.read_csv(processed_csv)
        except Exception:
            dfp = pd.DataFrame()
    else:
        dfp = pd.DataFrame()

    if rows:
        df_new = pd.DataFrame(rows)
        if not dfp.empty:
            dfp = pd.concat([df_new, dfp], ignore_index=True).drop_duplicates(subset=['Filename'], keep='first')
        else:
            dfp = df_new
            
        dfp.to_csv(processed_csv, index=False)
        print(f'Tagged/updated {updated} files. processed_files.csv updated with {len(rows)} entries.')
    else:
        print('No files needed tagging or updating.')
