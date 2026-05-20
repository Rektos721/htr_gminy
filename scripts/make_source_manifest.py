from __future__ import annotations

import argparse
import csv
from pathlib import Path

EXTS = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Tworzy prosty manifest źródłowy z folderu obrazów.")
    parser.add_argument("--input-dir", required=True, type=Path)
    parser.add_argument("--output-csv", required=True, type=Path)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    images = sorted(p for p in args.input_dir.resolve().iterdir() if p.suffix.lower() in EXTS)
    if not images:
        raise SystemExit(f"Brak obrazów w {args.input_dir}")
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.output_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["source"])
        for p in images:
            writer.writerow([str(p)])
    print(f"Zapisano {len(images)} wpisow -> {args.output_csv}")


if __name__ == "__main__":
    main()
