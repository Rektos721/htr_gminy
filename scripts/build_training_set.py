from __future__ import annotations

import argparse
import csv
import shutil
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Builds a Kraken/Ketos path-format training set.")
    parser.add_argument("--review-manifest", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--status", default="ready")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    manifest_path = args.review_manifest.resolve()
    output_dir = args.output_dir.resolve()
    gt_dir = output_dir / "ground-truth"
    gt_dir.mkdir(parents=True, exist_ok=True)

    if not manifest_path.exists():
        raise SystemExit(f"Review manifest not found: {manifest_path}")

    built = 0
    skipped = 0
    dataset_csv = output_dir / "dataset_manifest.csv"

    with manifest_path.open("r", encoding="utf-8", newline="") as handle, dataset_csv.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as out_handle:
        reader = csv.DictReader(handle)
        writer = csv.writer(out_handle)
        writer.writerow(["image", "gt_text", "status"])

        for row in reader:
            image_path = Path(row["image"])
            manual_text_path = Path(row["manual_text_path"])
            status = row.get("status", "").strip()

            if status and status != args.status:
                skipped += 1
                continue
            if not image_path.exists() or not manual_text_path.exists():
                skipped += 1
                continue

            text = manual_text_path.read_text(encoding="utf-8", errors="ignore").strip()
            if not text:
                skipped += 1
                continue

            dst_image = gt_dir / image_path.name
            dst_text = gt_dir / f"{image_path.stem}.gt.txt"
            shutil.copy2(image_path, dst_image)
            dst_text.write_text(text, encoding="utf-8")
            writer.writerow([str(dst_image), str(dst_text), status or args.status])
            built += 1
            print(f"added: {image_path.name}")

    print(f"built={built} skipped={skipped}")


if __name__ == "__main__":
    main()
