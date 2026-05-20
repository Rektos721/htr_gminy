from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Łączy wyniki Gemini OCR z wyciętymi komórkami tabeli."
    )
    parser.add_argument("--ocr-csv", required=True, type=Path, help="Wyjście z gemini_ocr_pages.py")
    parser.add_argument("--cells-manifest", required=True, type=Path, help="Wyjście z split_column_cells.py")
    parser.add_argument("--output-csv", required=True, type=Path)
    return parser


def main() -> None:
    args = build_parser().parse_args()

    # Załaduj OCR: klucz = (stem_źródła, row), wartość = lista kolumn
    ocr: dict[tuple[str, int], list[str]] = {}
    with args.ocr_csv.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            stem = Path(row["source"]).stem
            try:
                r = int(row["row"])
                cols = json.loads(row["cols_json"])
                ocr[(stem, r)] = cols
            except (ValueError, json.JSONDecodeError):
                pass

    # Załaduj manifest komórek i dopasuj
    results: list[dict] = []
    matched = 0
    total = 0

    with args.cells_manifest.open(encoding="utf-8", newline="") as f:
        for cell in csv.DictReader(f):
            total += 1
            stem = Path(cell["source"]).stem
            row_idx = int(cell["row_index"])
            col_idx = int(cell["col_index"])

            cols = ocr.get((stem, row_idx), [])
            text = cols[col_idx - 1] if col_idx - 1 < len(cols) else ""
            if text:
                matched += 1

            results.append({
                "cell_image": cell["cell_image"],
                "source": cell["source"],
                "row_index": row_idx,
                "col_index": col_idx,
                "ocr_guess": text,
                "manual_text": "",
                "status": "",
            })

    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.output_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)

    print(f"Komorek: {total}, dopasowanych OCR: {matched} ({100*matched//total}%) -> {args.output_csv}")


if __name__ == "__main__":
    main()
