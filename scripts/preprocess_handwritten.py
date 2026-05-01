from __future__ import annotations

import argparse
import csv
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps


SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp"}


def iter_images(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTS
    )


def prepare_image(
    src: Path,
    dst: Path,
    upscale: float,
    threshold: int | None,
    sharpen: bool,
) -> tuple[int, int]:
    image = Image.open(src).convert("L")
    image = ImageOps.exif_transpose(image)
    image = ImageOps.autocontrast(image)

    if upscale != 1.0:
        width = max(1, int(image.width * upscale))
        height = max(1, int(image.height * upscale))
        image = image.resize((width, height), Image.Resampling.LANCZOS)

    image = image.filter(ImageFilter.MedianFilter(size=3))

    if sharpen:
        image = image.filter(ImageFilter.UnsharpMask(radius=1.4, percent=180, threshold=3))

    if threshold is not None:
        image = image.point(lambda px: 255 if px >= threshold else 0)

    dst.parent.mkdir(parents=True, exist_ok=True)
    image.save(dst)
    return image.width, image.height


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepares handwritten table scans for HTR.")
    parser.add_argument("--input-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--upscale", type=float, default=1.5)
    parser.add_argument("--threshold", type=int, default=None)
    parser.add_argument("--no-sharpen", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    input_dir: Path = args.input_dir.resolve()
    output_dir: Path = args.output_dir.resolve()

    images = iter_images(input_dir)
    if not images:
        raise SystemExit(f"No supported images found in {input_dir}")

    manifest_path = output_dir / "manifest.csv"
    output_dir.mkdir(parents=True, exist_ok=True)

    with manifest_path.open("w", newline="", encoding="utf-8") as manifest_file:
        writer = csv.writer(manifest_file)
        writer.writerow(["source", "prepared", "width", "height"])

        for src in images:
            relative = src.relative_to(input_dir)
            dst = output_dir / relative.with_suffix(".png")
            width, height = prepare_image(
                src=src,
                dst=dst,
                upscale=args.upscale,
                threshold=args.threshold,
                sharpen=not args.no_sharpen,
            )
            writer.writerow([str(src), str(dst), width, height])
            print(f"prepared: {src.name} -> {dst.name} ({width}x{height})")


if __name__ == "__main__":
    main()
