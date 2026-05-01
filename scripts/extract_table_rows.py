from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps


SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp"}


def iter_images(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTS
    )


def detect_row_bands(
    image: Image.Image,
    ink_threshold: int,
    min_gap: int,
    min_height: int,
    analysis_scale: float,
) -> list[tuple[int, int]]:
    if analysis_scale <= 0 or analysis_scale > 1:
        raise ValueError("analysis_scale must be in (0, 1].")

    if analysis_scale != 1.0:
        scaled_width = max(1, int(image.width * analysis_scale))
        scaled_height = max(1, int(image.height * analysis_scale))
        analysis_image = image.resize((scaled_width, scaled_height), Image.Resampling.BILINEAR)
    else:
        analysis_image = image

    bw = analysis_image.point(lambda px: 0 if px < ink_threshold else 255)
    width, height = bw.size
    data = np.array(bw, dtype=np.uint8)
    rows = (data == 0).sum(axis=1)

    bands: list[tuple[int, int]] = []
    start: int | None = None
    gap = 0
    ink_floor = max(8, width // 150)

    for y, ink in enumerate(rows):
        if ink > ink_floor:
            if start is None:
                start = y
            gap = 0
        elif start is not None:
            gap += 1
            if gap >= min_gap:
                end = y - gap
                if end - start + 1 >= min_height:
                    bands.append((start, end))
                start = None
                gap = 0

    if start is not None:
        end = height - 1
        if end - start + 1 >= min_height:
            bands.append((start, end))

    merged: list[tuple[int, int]] = []
    for band in bands:
        if not merged:
            merged.append(band)
            continue
        prev_start, prev_end = merged[-1]
        curr_start, curr_end = band
        if curr_start - prev_end <= min_gap:
            merged[-1] = (prev_start, curr_end)
        else:
            merged.append(band)
    if analysis_scale == 1.0:
        return merged

    scale_back = 1.0 / analysis_scale
    restored: list[tuple[int, int]] = []
    for top, bottom in merged:
        restored_top = max(0, int(top * scale_back))
        restored_bottom = min(image.height - 1, int((bottom + 1) * scale_back))
        restored.append((restored_top, restored_bottom))
    return restored


def crop_rows(
    src: Path,
    dst_dir: Path,
    ink_threshold: int,
    min_gap: int,
    min_height: int,
    pad: int,
    analysis_scale: float,
) -> list[tuple[str, str, int, int]]:
    image = Image.open(src).convert("L")
    image = ImageOps.exif_transpose(image)
    bands = detect_row_bands(
        image,
        ink_threshold=ink_threshold,
        min_gap=min_gap,
        min_height=min_height,
        analysis_scale=analysis_scale,
    )

    rows_meta: list[tuple[str, str, int, int]] = []
    stem_dir = dst_dir / src.stem
    stem_dir.mkdir(parents=True, exist_ok=True)

    for idx, (top, bottom) in enumerate(bands, start=1):
        crop_top = max(0, top - pad)
        crop_bottom = min(image.height, bottom + pad + 1)
        row_image = image.crop((0, crop_top, image.width, crop_bottom))
        row_path = stem_dir / f"{src.stem}_row_{idx:03d}.png"
        row_image.save(row_path)
        rows_meta.append((str(src), str(row_path), crop_top, crop_bottom))

    return rows_meta


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Extracts rough handwritten table row bands.")
    parser.add_argument("--input-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--ink-threshold", type=int, default=165)
    parser.add_argument("--min-gap", type=int, default=18)
    parser.add_argument("--min-height", type=int, default=28)
    parser.add_argument("--pad", type=int, default=12)
    parser.add_argument("--analysis-scale", type=float, default=0.35)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    input_dir: Path = args.input_dir.resolve()
    output_dir: Path = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    images = iter_images(input_dir)
    if not images:
        raise SystemExit(f"No supported images found in {input_dir}")

    manifest_path = output_dir / "rows_manifest.csv"
    with manifest_path.open("w", newline="", encoding="utf-8") as manifest_file:
        writer = csv.writer(manifest_file)
        writer.writerow(["source", "row_image", "top", "bottom"])

        for src in images:
            rows_meta = crop_rows(
                src=src,
                dst_dir=output_dir,
                ink_threshold=args.ink_threshold,
                min_gap=args.min_gap,
                min_height=args.min_height,
                pad=args.pad,
                analysis_scale=args.analysis_scale,
            )
            for row in rows_meta:
                writer.writerow(row)
            print(f"rows: {src.name} -> {len(rows_meta)}")


if __name__ == "__main__":
    main()
