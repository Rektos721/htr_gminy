import csv, json
from pathlib import Path

MANIFEST = Path(r'C:\Users\Nocna\htr_gminy\outputs\training\training_manifest.csv')
OCR_CSV  = Path(r'C:\Users\Nocna\htr_gminy\outputs\ocr_pages.csv')

# OCR dla strony 13
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

print(f'OCR strony 13: wiersze {min(ocr13)}-{max(ocr13)}, liczba={len(ocr13)}')
print('Pierwsze 5 OCR:')
for k in sorted(ocr13)[:5]:
    print(f'  OCR[{k}]: {ocr13[k][:80]}')

# Manifest dla strony 13
with MANIFEST.open(encoding='utf-8', newline='') as f:
    rows13 = [r for r in csv.DictReader(f) if '384_13_' in r['source']]

print(f'\nManifest strony 13: {len(rows13)} wierszy')
print(f'Cluster row IDs: {sorted(int(r["row"]) for r in rows13)}')
print('\nPierwsze 5 z manifestu:')
for r in sorted(rows13, key=lambda x: int(x['row']))[:5]:
    cid = int(r['row'])
    gt_file = Path(r['manual_text_path'])
    gt_content = gt_file.read_text(encoding='utf-8').strip()[:80] if gt_file.exists() else '(brak pliku)'
    print(f'  cluster={cid}, img={Path(r["image"]).name}')
    print(f'    gt.txt: {gt_content}')
    print(f'    OCR[{cid}]: {ocr13.get(cid, "(brak)")[:80]}')
    # Jaki OCR pasuje do tej pozycji wizualnie?
    # Sprawdz czy w gt.txt jest numer rekordu i porownaj
