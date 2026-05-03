from __future__ import annotations

import argparse
import csv
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Buduje manifest review z OCR guessami z Gemini."
    )
    parser.add_argument("--gemini-csv", required=True, type=Path,
                        help="ocr_guesses.csv z gemini_ocr_cells.py")
    parser.add_argument("--output-dir", required=True, type=Path,
                        help="Katalog wyjściowy (manifest + cell-transcriptions/)")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    gemini_csv = args.gemini_csv.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    gt_dir = output_dir / "cell-transcriptions"
    gt_dir.mkdir(parents=True, exist_ok=True)

    rows = list(csv.DictReader(gemini_csv.open(encoding="utf-8", newline="")))

    output_manifest = output_dir / "review_manifest.csv"
    skipped = 0
    written = 0

    with output_manifest.open("w", encoding="utf-8", newline="") as out_handle:
        writer = csv.writer(out_handle)
        writer.writerow([
            "image", "source", "left", "top", "right", "bottom",
            "ocr_guess", "manual_text_path", "status", "notes",
        ])

        for row in rows:
            guess = row.get("ocr_guess", "").strip()

            # pomiń śmieci których Gemini nie odczytał
            if guess in ("[błąd]", "[brak pliku]", "[puste]", ""):
                skipped += 1
                continue

            cell_image = Path(row["cell_image"])
            text_path = gt_dir / f"{cell_image.stem}.gt.txt"

            # pre-wypełnij .gt.txt guessem — recenzent tylko poprawia
            if not text_path.exists() or text_path.read_text(encoding="utf-8").strip() == "":
                text_path.write_text(guess, encoding="utf-8")

            notes = f"r{int(row['row_index']):03d} c{int(row['col_index']):03d}"

            writer.writerow([
                str(cell_image),
                row.get("source", ""),
                row.get("left", ""),
                row.get("top", ""),
                row.get("right", ""),
                row.get("bottom", ""),
                guess,
                str(text_path),
                "todo",
                notes,
            ])
            written += 1

    print(f"Zapisano: {written} komórek, pominięto pustych/błędów: {skipped}")
    print(f"Manifest: {output_manifest}")
    print(f"Pliki .gt.txt: {gt_dir}")


if __name__ == "__main__":
    main()
