"""
Naprawa strony 13: poprawny offset to +35, nie +26.
Klastry 9-35, OCR 35-69.
- Skipped klaster (0) -> OCR[35] (wizualny naglowek kolumn strony)
- Klaster 1 -> OCR[36], ..., klaster 9 -> OCR[44], ..., klaster 34 -> OCR[69]
- Klaster 35 -> OCR[70] (nie istnieje -> pusty)
"""
import csv, json
from pathlib import Path

MANIFEST = Path(r'C:\Users\Nocna\htr_gminy\outputs\training\training_manifest.csv')
OCR_CSV  = Path(r'C:\Users\Nocna\htr_gminy\outputs\ocr_pages.csv')

CORRECT_OFFSET = 35

# OCR strony 13
ocr13 = {}
with OCR_CSV.open(encoding='utf-8', newline='') as f:
    for row in csv.DictReader(f):
        if '384_13_' not in row['source']:
            continue
        try:
            r = int(row['row'])
            cols = json.loads(row['cols_json'])
            text = ' | '.join(str(c).strip() for c in cols if str(c).strip())
            ocr13[r] = text
        except Exception:
            pass

print(f'OCR strony 13: wiersze {min(ocr13)}-{max(ocr13)}')

# Wczytaj manifest
with MANIFEST.open(encoding='utf-8', newline='') as f:
    reader = csv.DictReader(f)
    fieldnames = list(reader.fieldnames)
    rows = list(reader)

updated = 0
for row in rows:
    if '384_13_' not in row['source']:
        continue
    cid = int(row['row'])
    ocr_idx = cid + CORRECT_OFFSET
    text = ocr13.get(ocr_idx, '')
    row['gt_text'] = text
    row['has_text'] = str(bool(text))
    gt = Path(row['manual_text_path'])
    gt.write_text(text, encoding='utf-8')
    print(f'  klaster {cid} -> OCR[{ocr_idx}]: {text[:60]}')
    updated += 1

with MANIFEST.open('w', encoding='utf-8', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
    writer.writeheader()
    writer.writerows(rows)

print(f'\nNaprawiono {updated} wierszy strony 13 (offset={CORRECT_OFFSET:+d})')
