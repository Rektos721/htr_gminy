"""
Konwertuje dataset POPP do formatu path (TIF/PNG + .gt.txt).

Struktura POPP:
  data/<Subset>/lines/labels.json  → ground_truth.{train,valid,test}[filename] = {text: ...}
  data/<Subset>/lines/train/*.tif
  data/<Subset>/lines/valid/*.tif
  data/<Subset>/lines/test/*.tif

Użycie:
    python scripts/convert_popp.py \
        --popp-dir external_data/popp/data \
        --output-dir outputs/training/ground-truth/popp \
        --splits train valid
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--popp-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--splits", nargs="+", default=["train"],
                        help="train valid test (domyślnie tylko train)")
    return parser


def convert(popp_dir: Path, output_dir: Path, splits: list[str]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    total = 0

    for subset_dir in sorted(popp_dir.iterdir()):
        if not subset_dir.is_dir():
            continue
        lines_dir = subset_dir / "lines"
        label_file = lines_dir / "labels.json"
        if not label_file.exists():
            continue

        with open(label_file, encoding="utf-8", errors="replace") as f:
            data = json.load(f)

        ground_truth = data.get("ground_truth", {})
        converted = 0

        for split in splits:
            split_items = ground_truth.get(split, {})
            split_dir = lines_dir / split

            for filename, meta in split_items.items():
                text = meta.get("text", "").strip()
                if not text:
                    continue

                src = split_dir / filename
                if not src.exists():
                    continue

                stem = f"popp_{subset_dir.name}_{split}_{Path(filename).stem}"
                dst_img = output_dir / f"{stem}{src.suffix}"
                dst_gt = output_dir / f"{stem}.gt.txt"

                shutil.copy2(src, dst_img)
                dst_gt.write_text(text, encoding="utf-8")
                converted += 1

        print(f"{subset_dir.name}: {converted} linii")
        total += converted

    print(f"\nRazem: {total} linii → {output_dir}")


def main() -> None:
    args = build_parser().parse_args()
    popp_dir = args.popp_dir.resolve()
    output_dir = args.output_dir.resolve()
    if not popp_dir.exists():
        raise SystemExit(f"POPP dir not found: {popp_dir}")
    convert(popp_dir, output_dir, args.splits)


if __name__ == "__main__":
    main()
