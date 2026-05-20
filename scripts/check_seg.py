import json, sys
path = sys.argv[1] if len(sys.argv) > 1 else "C:/Users/Nocna/htr_gminy/outputs/seg_test.json"
with open(path) as f:
    data = json.load(f)
lines = data.get("lines", [])
print("Wykryte linie:", len(lines))
for i, line in enumerate(lines[:8], 1):
    bl = line.get("baseline", [])
    print(f"  Linia {i}: {len(bl)} pkt baseline, bbox={line.get('bbox','')}")
