import csv, json
from pathlib import Path
from collections import defaultdict

MANIFEST = Path(r'C:\Users\Nocna\htr_gminy\outputs\training\training_manifest.csv')
OCR_CSV  = Path(r'C:\Users\Nocna\htr_gminy\outputs\ocr_pages.csv')

ocr = defaultdict(dict)
with OCR_CSV.open(encoding='utf-8', newline='') as f:
    for row in csv.DictReader(f):
        stem = Path(row['source']).stem
        try:
            r = int(row['row'])
            cols = json.loads(row['cols_json'])
            text = ' | '.join(str(c).strip() for c in cols if str(c).strip())
            ocr[stem][r] = text
        except Exception:
            pass

rows = []
with MANIFEST.open(encoding='utf-8', newline='') as f:
    reader = csv.DictReader(f)
    fieldnames = list(reader.fieldnames)
    rows = list(reader)

remaining = [r for r in rows if r.get('status', '') != 'ready']
by_page = defaultdict(list)
for r in remaining:
    by_page[r['source']].append(r)

print(f'Pozostale strony: {len(by_page)}, wierszy: {len(remaining)}')
for src, page_rows in sorted(by_page.items()):
    stem = Path(src).stem
    page_ocr = ocr.get(stem, {})
    cluster_ids = sorted(int(r['row']) for r in page_rows)
    ocr_ids = sorted(page_ocr.keys())
    if not ocr_ids:
        print(f'  {stem}: BRAK OCR')
        continue
    max_c = max(cluster_ids)
    min_o, max_o = min(ocr_ids), max(ocr_ids)
    has_text = sum(1 for r in page_rows if r.get('gt_text', '').strip())
    # Sprawdz najlepszy offset (-2..+2)
    best_off, best_match = 0, -1
    for off in range(-3, 4):
        matches = sum(1 for cid in cluster_ids if page_ocr.get(cid + off, '').strip())
        if matches > best_match:
            best_match, best_off = matches, off
    current_match = sum(1 for cid in cluster_ids if page_ocr.get(cid, '').strip())
    flag = '' if best_off == 0 else f'  <-- OFFSET {best_off:+d} ({current_match}->{best_match} z tekstem)'
    print(f'  {stem[-18:]}: klastry={len(cluster_ids)} ocr={min_o}-{max_o} manifest_text={has_text}{flag}')
