import csv
from pathlib import Path

manifest = Path(r"C:\Users\Nocna\htr_gminy\outputs\training\training_manifest.csv")
page = "92_54_0_15_384_10_105647064.jpg"

ocr = {
    1: "1 | 1P | 36 | Wysoki obrew | Hałajdziak Ludwik | Franciszkia",
    2: "2 | 17 | 36 | „ | „ Stanisława | Ludwik",
    3: "3 | 17 | 13 | „ | Hadrys Henryk | Jan Helena",
}

rows = []
with manifest.open(encoding="utf-8", newline="") as f:
    reader = csv.DictReader(f)
    fieldnames = list(reader.fieldnames)
    for row in reader:
        rows.append(row)

new_rows = []
for row in rows:
    if row["source"] != page:
        new_rows.append(row)
        continue
    ridx = int(row["row"])
    if ridx == 1:
        img = Path(row["image"])
        gt = img.with_suffix(".gt.txt")
        if img.exists():
            img.unlink()
        if gt.exists():
            gt.unlink()
        print(f"DELETED: {img.name}")
        continue
    new_ocr_idx = ridx - 1
    text = ocr.get(new_ocr_idx, "")
    row["gt_text"] = text
    row["has_text"] = str(bool(text))
    gt = Path(row["image"]).with_suffix(".gt.txt")
    gt.write_text(text, encoding="utf-8")
    new_rows.append(row)
    print(f"  row {ridx} -> OCR {new_ocr_idx}: {text[:50]}")

with manifest.open("w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(new_rows)

print(f"\nManifest: {len(rows)} -> {len(new_rows)} wierszy")
