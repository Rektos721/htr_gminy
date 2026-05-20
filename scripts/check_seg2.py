import json

with open("C:/Users/Nocna/htr_gminy/outputs/seg_test.json") as f:
    data = json.load(f)

lines = data.get("lines", [])
print("Linie:", len(lines))
print("Klucze linii:", list(lines[0].keys()) if lines else "brak")
print()
# pokaz pierwsze 10 z wspolrzednymi
for i, line in enumerate(lines[:10], 1):
    bl = line.get("baseline", [])
    mask = line.get("boundary", line.get("mask", []))
    print(f"Linia {i}: baseline={bl[:3]}... boundary_pts={len(mask)}")
