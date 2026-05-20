"""
1. Usuwa z manifestu wiersze ze statusem 'ready'
2. Dla kazdej pozostalej strony: porownuje zawartosc .gt.txt z ocr_pages.csv
   i wykrywa offset. Stosuje poprawke jesli offset != 0.
"""
import csv, json
from pathlib import Path
from collections import defaultdict

MANIFEST = Path(r'C:\Users\Nocna\htr_gminy\outputs\training\training_manifest.csv')
OCR_CSV  = Path(r'C:\Users\Nocna\htr_gminy\outputs\ocr_pages.csv')

# --- Wczytaj OCR ---
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

# --- Wczytaj manifest ---
with MANIFEST.open(encoding='utf-8', newline='') as f:
    reader = csv.DictReader(f)
    fieldnames = list(reader.fieldnames)
    rows = list(reader)

total_before = len(rows)

# --- Krok 1: Usun 'ready' ---
kept = [r for r in rows if r.get('status', '') != 'ready']
removed = total_before - len(kept)
print(f'Usunieto z manifestu: {removed} wierszy ze statusem ready')
print(f'Pozostalo: {len(kept)} wierszy')

# --- Krok 2: Wykryj i napraw offset per strona ---
by_page = defaultdict(list)
for r in kept:
    by_page[r['source']].append(r)

def best_offset(cluster_ids, page_ocr, search_range=35):
    best_off, best_match = 0, -1
    for off in range(-search_range, search_range + 1):
        matches = sum(1 for cid in cluster_ids if page_ocr.get(cid + off, '').strip())
        if matches > best_match:
            best_match, best_off = matches, off
    return best_off, best_match

fixed_pages = 0
for src, page_rows in sorted(by_page.items()):
    stem = Path(src).stem
    page_ocr = ocr.get(stem, {})
    if not page_ocr:
        print(f'  {stem[-18:]}: BRAK OCR, pomijam')
        continue

    cluster_ids = [int(r['row']) for r in page_rows]
    current_match = sum(1 for cid in cluster_ids if page_ocr.get(cid, '').strip())
    off, best_match = best_offset(cluster_ids, page_ocr)

    if off == 0:
        print(f'  {stem[-18:]}: OK (offset=0, text={current_match}/{len(cluster_ids)})')
        continue

    # Sprawdz czy faktycznie warto naprawiac (poprawa > 0 wierszy z tekstem)
    if best_match <= current_match:
        print(f'  {stem[-18:]}: offset={off:+d} nie poprawia ({current_match}={best_match}), pomijam')
        continue

    print(f'  {stem[-18:]}: NAPRAWA offset={off:+d} ({current_match} -> {best_match} z tekstem)')

    for row in page_rows:
        cid = int(row['row'])
        new_ocr_idx = cid + off
        text = page_ocr.get(new_ocr_idx, '')
        row['gt_text'] = text
        row['has_text'] = str(bool(text))
        gt = Path(row['manual_text_path'])
        gt.write_text(text, encoding='utf-8')

    fixed_pages += 1

# --- Zapisz manifest ---
with MANIFEST.open('w', encoding='utf-8', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
    writer.writeheader()
    writer.writerows(kept)

print(f'\nGotowe: usunieto {removed}, naprawiono {fixed_pages} stron, manifest={len(kept)} wierszy')
with_text = sum(1 for r in kept if r.get('gt_text', '').strip())
print(f'Z tekstem OCR: {with_text}/{len(kept)}')
