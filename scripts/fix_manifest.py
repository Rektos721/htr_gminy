"""
Czyści training_manifest.csv:
- usuwa strony 2-9 (tylko druk, zero danych ręcznych)
- naprawia stronę 13 (OCR numerowane 35-69, klastry 1-35 -> offset 34)
"""
import csv
from pathlib import Path

MANIFEST = Path(r"C:\Users\Nocna\htr_gminy\outputs\training\training_manifest.csv")
OCR_CSV  = Path(r"C:\Users\Nocna\htr_gminy\outputs\ocr_pages.csv")

# Wczytaj OCR dla strony 13
ocr_page13: dict[int, str] = {}
with OCR_CSV.open(encoding="utf-8", newline="") as f:
    import json
    for row in csv.DictReader(f):
        if "384_13_" not in row["source"]:
            continue
        try:
            r = int(row["row"])
            cols = json.loads(row["cols_json"])
            text = " | ".join(str(c).strip() for c in cols if str(c).strip())
            ocr_page13[r] = text
        except (ValueError, json.JSONDecodeError):
            pass

print(f"OCR page 13: wiersze {min(ocr_page13)} - {max(ocr_page13)}")
offset13 = min(ocr_page13) - 1  # np. 34 jeśli OCR zaczyna od 35

REMOVE_PAGES = {f"384_{p}_" for p in range(2, 10)}

rows = []
with MANIFEST.open(encoding="utf-8", newline="") as f:
    reader = csv.DictReader(f)
    fieldnames = list(reader.fieldnames)
    rows = list(reader)

deleted_files = 0
new_rows = []
fixed_page13 = 0

for row in rows:
    src = row["source"]

    # Usuń strony 2-9
    if any(pat in src for pat in REMOVE_PAGES):
        for ext in [".png", ".gt.txt"]:
            p = Path(row["image"]).with_suffix(ext)
            if p.exists():
                p.unlink()
                deleted_files += 1
        continue

    # Napraw stronę 13
    if "384_13_" in src:
        cluster_idx = int(row["row"])
        ocr_idx = cluster_idx + offset13
        text = ocr_page13.get(ocr_idx, "")
        row["gt_text"] = text
        row["has_text"] = str(bool(text))
        gt = Path(row["image"]).with_suffix(".gt.txt")
        gt.write_text(text, encoding="utf-8")
        if text:
            fixed_page13 += 1

    new_rows.append(row)

with MANIFEST.open("w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(new_rows)

print(f"Usunieto wierszy: {len(rows) - len(new_rows)} (pliki: {deleted_files})")
print(f"Naprawiono page 13: {fixed_page13} wierszy z tekstem")
print(f"Manifest: {len(new_rows)} wierszy")
with_text = sum(1 for r in new_rows if r["has_text"] == "True")
print(f"Z tekstem OCR: {with_text}")
