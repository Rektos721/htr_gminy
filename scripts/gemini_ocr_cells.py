from __future__ import annotations

import csv
import os
import re
import sys
import time
from pathlib import Path

from google import genai
from google.genai import types

API_KEY = os.environ.get("GEMINI_API_KEY", "")
MODEL = "gemini-2.0-flash"
CELLS_MANIFEST = Path(r"C:\Users\Nocna\source\handwritten-htr\outputs\cells-grid-v6\cells_manifest.csv")
OUTPUT_CSV = Path(r"C:\Users\Nocna\source\handwritten-htr\outputs\cells-grid-v6\ocr_guesses.csv")
RPM_DELAY = 5.0   # 60s / 15 RPM + margines
MAX_RETRIES = 4

PROMPT = (
    "To jest wycięta komórka z odręcznie wypełnionej tabeli urzędowej. "
    "Przepisz dokładnie tekst który widzisz. "
    "Jeśli komórka jest pusta lub nie możesz nic odczytać, napisz tylko: [puste]. "
    "Nie dodawaj żadnych komentarzy ani wyjaśnień — tylko sam tekst."
)

client = genai.Client(api_key=API_KEY)


def extract_retry_delay(exc: Exception) -> float:
    match = re.search(r"retryDelay.*?(\d+(?:\.\d+)?)\s*s", str(exc))
    if match:
        return float(match.group(1)) + 2.0
    return 15.0


def ocr_cell(image_path: Path) -> str:
    image_bytes = image_path.read_bytes()
    for attempt in range(MAX_RETRIES):
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=[
                    types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
                    PROMPT,
                ],
            )
            return response.text.strip()
        except Exception as exc:
            if "429" in str(exc) and attempt < MAX_RETRIES - 1:
                wait = extract_retry_delay(exc)
                print(f"  rate limit, czekam {wait:.0f}s...", flush=True)
                time.sleep(wait)
            else:
                raise
    return "[błąd]"


def load_existing(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    done = {}
    for row in csv.DictReader(path.open(encoding="utf-8", newline="")):
        if row.get("ocr_guess") and row["ocr_guess"] != "[błąd]":
            done[row["cell_image"]] = row["ocr_guess"]
    return done


def main() -> None:
    rows = list(csv.DictReader(CELLS_MANIFEST.open(encoding="utf-8", newline="")))
    total = len(rows)
    existing = load_existing(OUTPUT_CSV)
    print(f"Komórek: {total}, już zrobionych: {len(existing)}", flush=True)

    fieldnames = list(rows[0].keys())
    if "ocr_guess" not in fieldnames:
        fieldnames.append("ocr_guess")

    out_rows = []
    done_count = 0
    for i, row in enumerate(rows, start=1):
        cell_path = Path(row["cell_image"])
        key = row["cell_image"]

        if key in existing:
            row["ocr_guess"] = existing[key]
            out_rows.append(row)
            continue

        if not cell_path.exists():
            row["ocr_guess"] = "[brak pliku]"
            out_rows.append(row)
            continue

        try:
            guess = ocr_cell(cell_path)
            row["ocr_guess"] = guess
            done_count += 1
            print(f"[{i}/{total}] {cell_path.name}: {guess[:70]}", flush=True)
        except Exception as exc:
            print(f"[{i}/{total}] BŁĄD {cell_path.name}: {exc}", flush=True)
            row["ocr_guess"] = "[błąd]"

        out_rows.append(row)

        # zapisz co iterację żeby nie stracić postępu
        with OUTPUT_CSV.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(out_rows)

        if i < total:
            time.sleep(RPM_DELAY)

    print(f"\nGotowe. Nowych: {done_count}, wyniki: {OUTPUT_CSV}", flush=True)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
