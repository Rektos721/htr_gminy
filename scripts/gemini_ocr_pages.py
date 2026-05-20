from __future__ import annotations

import argparse
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
DELAY = 6.0

PROMPT = """To jest strona z odręcznie wypełnionej tabeli urzędowej z archiwum gminy (warunki zabudowy, decyzje o warunkach zabudowy lub podobne dokumenty administracyjne).

Przepisz WSZYSTKIE dane z tabeli dokładnie tak jak są zapisane. Pomiń nagłówki kolumn — interesują nas tylko wiersze z danymi.

Każdy wiersz zapisz jako obiekt JSON:
{"r": numer_wiersza_zaczynajac_od_1, "cols": ["wartość_kol1", "wartość_kol2", ...]}

Zasady:
- Przepisuj dokładnie: numery działek, adresy, nazwiska, daty, numery decyzji — wszystko bez zmian
- Pusta komórka → ""
- Nieczytelna komórka → "?"
- Kolumny zachowaj w kolejności od lewej do prawej
- Nie interpretuj, nie uzupełniaj, nie poprawiaj — tylko przepisuj

Zwróć TYLKO tablicę JSON, bez żadnego tekstu przed ani po.

Przykład:
[
  {"r": 1, "cols": ["1", "2024-03-15", "Kowalski Jan", "ul. Różana 5, Kraków", "dz. nr 123/4 obr. 0012", "WZ/2024/001", "pozytywna"]},
  {"r": 2, "cols": ["2", "2024-03-16", "Nowak Anna", "os. Słoneczne 12/3, Kraków", "dz. nr 567 obr. 0034", "WZ/2024/002", ""]}
]"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="OCR całych stron tabeli przez Gemini (warunki zabudowy)."
    )
    parser.add_argument("--input-dir", required=True, type=Path, help="Folder z obrazami stron (PNG/JPG)")
    parser.add_argument("--output-csv", required=True, type=Path, help="Wyjściowy plik CSV z wynikami")
    parser.add_argument("--delay", type=float, default=DELAY, help="Opóźnienie między requestami (s)")
    return parser


def parse_json_response(text: str) -> list[dict]:
    text = text.strip()
    match = re.search(r'\[.*\]', text, re.DOTALL)
    if match:
        text = match.group(0)
    return json.loads(text)


def ocr_page(client: genai.Client, image_path: Path) -> list[dict]:
    image_bytes = image_path.read_bytes()
    suffix = image_path.suffix.lower()
    mime = "image/png" if suffix == ".png" else "image/jpeg"
    response = client.models.generate_content(
        model=MODEL,
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type=mime),
            PROMPT,
        ],
    )
    return parse_json_response(response.text)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    args = build_parser().parse_args()

    if not API_KEY:
        raise SystemExit("Brak GEMINI_API_KEY w środowisku.")

    client = genai.Client(api_key=API_KEY)
    input_dir = args.input_dir.resolve()
    output_csv = args.output_csv.resolve()

    images = sorted(input_dir.glob("*.png")) + sorted(input_dir.glob("*.jpg")) + sorted(input_dir.glob("*.jpeg"))
    if not images:
        raise SystemExit(f"Brak obrazów w {input_dir}")

    output_csv.parent.mkdir(parents=True, exist_ok=True)

    all_rows: list[dict] = []

    for img_path in images:
        print(f"\nPrzetwarzam: {img_path.name}", flush=True)
        try:
            page_rows = ocr_page(client, img_path)
            print(f"  Gemini zwrócił {len(page_rows)} wierszy", flush=True)
            for row in page_rows:
                all_rows.append({
                    "source": img_path.name,
                    "row": row.get("r", ""),
                    "cols_json": json.dumps(row.get("cols", []), ensure_ascii=False),
                })
                cols = row.get("cols", [])
                preview = " | ".join(str(c)[:20] for c in cols[:5])
                print(f"  r{row.get('r'):02d}: {preview}", flush=True)
        except Exception as exc:
            print(f"  BŁĄD: {exc}", flush=True)
            all_rows.append({"source": img_path.name, "row": "ERR", "cols_json": str(exc)})

        time.sleep(args.delay)

    with output_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["source", "row", "cols_json"])
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"\nGotowe. {len(all_rows)} wierszy → {output_csv}")


if __name__ == "__main__":
    main()
