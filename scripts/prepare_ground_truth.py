from __future__ import annotations

import argparse
import csv
from pathlib import Path


SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp"}


def iter_images(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTS
    )


def infer_ocr_text(image_path: Path, ocr_dir: Path) -> str:
    direct_match = ocr_dir / image_path.with_suffix(".txt").name
    if direct_match.exists():
        return direct_match.read_text(encoding="utf-8", errors="ignore")

    stem_match = list(ocr_dir.rglob(f"{image_path.stem}.txt"))
    if stem_match:
        return stem_match[0].read_text(encoding="utf-8", errors="ignore")
    return ""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepares a review pack for manual transcription fixes.")
    parser.add_argument("--images-dir", required=True, type=Path)
    parser.add_argument("--ocr-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    images_dir = args.images_dir.resolve()
    ocr_dir = args.ocr_dir.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    images = iter_images(images_dir)
    if not images:
        raise SystemExit(f"No supported images found in {images_dir}")

    review_csv = output_dir / "review_manifest.csv"
    text_dir = output_dir / "transcriptions"
    text_dir.mkdir(parents=True, exist_ok=True)

    with review_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "image",
                "ocr_guess",
                "manual_text_path",
                "status",
                "notes",
            ]
        )

        for image_path in images:
            guess = infer_ocr_text(image_path, ocr_dir).strip()
            txt_path = text_dir / f"{image_path.stem}.gt.txt"
            if not txt_path.exists():
                txt_path.write_text(guess, encoding="utf-8")
            writer.writerow([str(image_path), guess, str(txt_path), "todo", ""])
            print(f"ground-truth: {image_path.name}")


if __name__ == "__main__":
    main()
