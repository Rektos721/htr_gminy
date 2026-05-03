from __future__ import annotations

import csv
import json
import os
import re
import sys
import time
from pathlib import Path

from google import genai
from google.genai import types

API_KEY = os.environ.get("GEMINI_API_KEY", "")
MODEL = "gemini-2.5-flash"
CELLS_MANIFEST = Path(r"C:\Users\Nocna\source\handwritten-htr\outputs\cells-grid-v6\cells_manifest.csv")
OUTPUT_CSV = Path(r"C:\Users\Nocna\source\handwritten-htr\outputs\cells-grid-v6\ocr_guesses.csv")
DELAY = 5.0

PROMPT = """Ta strona zawiera odręcznie wypełnioną tabelę archiwalną.
Przepisz dane z tabeli. Pomiń nagłówki kolumn.
Każdy wiersz danych zapisz jako obiekt JSON w tej formie:
{"r": numer_wiersza_zaczynajac_od_1, "cols": ["wartość_kol1", "wartość_kol2", ...]}

Gdzie "cols" to lista WSZYSTKICH kolumn od lewej do prawej.
Jeśli kolumna jest pusta — wstaw pusty string "".
Jeśli czegoś nie możesz odczytać — wstaw "?".

Zwróć TYLKO listę JSON, bez żadnego dodatkowego tekstu.
Przykład:
[
  {"r": 1, "cols": ["36", "1", "Józef Janowski", "", "Ludwik i Tekla", "8", "marca", "1893"]},
  {"r": 2, "cols": ["", "2", "", "Wiktoria", "Józef i Antonina", "18", "stycznia", "1896"]}
]"""

client = genai.Client(api_key=API_KEY)


def parse_json_response(text: str) -> list[dict]:
    text = text.strip()
    # wyciągnij JSON nawet jeśli model dodał markdown
    match = re.search(r'\[.*\]', text, re.DOTALL)
    if match:
        text = match.group(0)
    return json.loads(text)


def ocr_page(image_path: Path) -> list[dict]:
    image_bytes = image_path.read_bytes()
    response = client.models.generate_content(
        model=MODEL,
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
            PROMPT,
        ],
    )
    return parse_json_response(response.text)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")

    rows = list(csv.DictReader(CELLS_MANIFEST.open(encoding="utf-8", newline="")))

    # grupuj komórki po źródle i wierszu
    by_source: dict[str, dict[int, dict[int, dict]]] = {}
    for row in rows:
        src = row["source"]
        r = int(row["row_index"])
        c = int(row["col_index"])
        by_source.setdefault(src, {}).setdefault(r, {})[c] = row

    # zbierz unikalne obrazy (prepared)
    # cells_manifest ma "source" = oryginalny jpg, potrzebujemy prepared png
    prepared_dir = Path(r"C:\Users\Nocna\source\handwritten-htr\samples\prepared")
    source_to_prepared: dict[str, Path] = {}
    for src in by_source:
        stem = Path(src).stem
        prepared = prepared_dir / f"{stem}.png"
        if prepared.exists():
            source_to_prepared[src] = prepared
        else:
            print(f"BRAK prepared: {stem}.png — pomijam")

    guesses: dict[str, str] = {}  # cell_image → ocr_guess

    for src, prepared_path in source_to_prepared.items():
        print(f"\nPrzetwarzam: {prepared_path.name}", flush=True)
        try:
            page_rows = ocr_page(prepared_path)
        except Exception as exc:
            print(f"  BŁĄD: {exc}", flush=True)
            continue

        print(f"  Gemini zwrócił {len(page_rows)} wierszy", flush=True)

        cell_rows = by_source[src]

        # przenumeruj col_index na sekwencyjne pozycje (0-based) per source
        all_col_indices = sorted({c for row in cell_rows.values() for c in row})
        col_to_seq = {c: i for i, c in enumerate(all_col_indices)}
        print(f"  Kolumny: {all_col_indices} → seq 0..{len(all_col_indices)-1}", flush=True)

        for page_row in page_rows:
            r_idx = page_row.get("r")
            cols_list = page_row.get("cols", [])
            if r_idx not in cell_rows:
                continue

            our_cells = cell_rows[r_idx]
            for c_idx, cell_row in our_cells.items():
                seq = col_to_seq[c_idx]
                if seq < len(cols_list):
                    text = cols_list[seq].strip()
                    if text and text != "?":
                        guesses[cell_row["cell_image"]] = text
                        print(f"  r{r_idx:02d} c{c_idx:02d}(seq{seq}): {text[:50]}", flush=True)

        time.sleep(DELAY)

    # zapisz wyniki
    fieldnames = list(rows[0].keys())
    if "ocr_guess" not in fieldnames:
        fieldnames.append("ocr_guess")

    with OUTPUT_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            row["ocr_guess"] = guesses.get(row["cell_image"], "")
            writer.writerow(row)

    filled = sum(1 for v in guesses.values() if v)
    print(f"\nGotowe. Wypełniono {filled}/{len(rows)} komórek → {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
