from __future__ import annotations

import argparse
import csv
from pathlib import Path

import cv2
import numpy as np


def cluster_positions(values: np.ndarray, tolerance: int) -> list[int]:
    if len(values) == 0:
        return []
    values = np.sort(values.astype(int))
    clusters: list[list[int]] = [[int(values[0])]]
    for value in values[1:]:
        if int(value) - clusters[-1][-1] <= tolerance:
            clusters[-1].append(int(value))
        else:
            clusters.append([int(value)])
    return [int(round(sum(cluster) / len(cluster))) for cluster in clusters]


def detect_lines(mask: np.ndarray, axis: int, threshold_ratio: float, tolerance: int) -> list[int]:
    if axis == 0:
        strength = (mask > 0).sum(axis=0)
        threshold = int(mask.shape[0] * threshold_ratio)
    else:
        strength = (mask > 0).sum(axis=1)
        threshold = int(mask.shape[1] * threshold_ratio)
    hits = np.where(strength >= threshold)[0]
    return cluster_positions(hits, tolerance=tolerance)


def build_masks(
    image: np.ndarray,
    adaptive_block_size: int,
    adaptive_c: int,
    horizontal_divisor: int,
    vertical_divisor: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    binary = cv2.adaptiveThreshold(
        image,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        adaptive_block_size,
        adaptive_c,
    )
    horizontal_kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT, (max(25, image.shape[1] // horizontal_divisor), 1)
    )
    vertical_kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT, (1, max(25, image.shape[0] // vertical_divisor))
    )
    horizontal = cv2.morphologyEx(binary, cv2.MORPH_OPEN, horizontal_kernel)
    vertical = cv2.morphologyEx(binary, cv2.MORPH_OPEN, vertical_kernel)
    return binary, horizontal, vertical


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Splits handwritten table pages into non-empty cell crops.")
    parser.add_argument("--columns-manifest", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--adaptive-block-size", type=int, default=35)
    parser.add_argument("--adaptive-c", type=int, default=11)
    parser.add_argument("--horizontal-divisor", type=int, default=28)
    parser.add_argument("--vertical-divisor", type=int, default=28)
    parser.add_argument("--row-threshold-ratio", type=float, default=0.12)
    parser.add_argument("--col-threshold-ratio", type=float, default=0.08)
    parser.add_argument("--line-cluster-tolerance", type=int, default=8)
    parser.add_argument("--skip-first-lines", type=int, default=2)
    parser.add_argument("--min-cell-width", type=int, default=50)
    parser.add_argument("--min-cell-height", type=int, default=40)
    parser.add_argument("--min-content-pixels", type=int, default=120)
    parser.add_argument("--min-content-ratio", type=float, default=0.004)
    parser.add_argument("--border-pad", type=int, default=3)
    parser.add_argument("--content-inner-margin", type=int, default=10)
    parser.add_argument("--crop-expand-x", type=int, default=10)
    parser.add_argument("--crop-expand-y", type=int, default=6)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    manifest_path = args.columns_manifest.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    with manifest_path.open("r", encoding="utf-8", newline="") as handle:
        sources = sorted({row["source"] for row in csv.DictReader(handle)})

    cells_manifest = output_dir / "cells_manifest.csv"
    with cells_manifest.open("w", encoding="utf-8", newline="") as out_handle:
        writer = csv.writer(out_handle)
        writer.writerow(
            [
                "source",
                "row_index",
                "col_index",
                "cell_image",
                "left",
                "top",
                "right",
                "bottom",
                "ink_pixels",
            ]
        )

        for source in sources:
            image = cv2.imread(source, cv2.IMREAD_GRAYSCALE)
            if image is None:
                raise SystemExit(f"Failed to read image: {source}")

            binary, horizontal, vertical = build_masks(
                image=image,
                adaptive_block_size=args.adaptive_block_size,
                adaptive_c=args.adaptive_c,
                horizontal_divisor=args.horizontal_divisor,
                vertical_divisor=args.vertical_divisor,
            )
            row_lines = detect_lines(
                mask=horizontal,
                axis=1,
                threshold_ratio=args.row_threshold_ratio,
                tolerance=args.line_cluster_tolerance,
            )
            col_lines = detect_lines(
                mask=vertical,
                axis=0,
                threshold_ratio=args.col_threshold_ratio,
                tolerance=args.line_cluster_tolerance,
            )

            if len(row_lines) <= args.skip_first_lines + 1 or len(col_lines) < 2:
                print(f"grid: {Path(source).name} -> insufficient lines ({len(row_lines)} rows, {len(col_lines)} cols)")
                continue

            row_lines = row_lines[args.skip_first_lines :]

            line_mask = cv2.bitwise_or(horizontal, vertical)
            line_mask = cv2.dilate(line_mask, np.ones((5, 5), np.uint8), iterations=1)
            content_mask = binary.copy()
            content_mask[line_mask > 0] = 0

            source_name = Path(source).stem
            source_dir = output_dir / source_name
            source_dir.mkdir(parents=True, exist_ok=True)

            kept = 0
            for row_idx, (top_line, bottom_line) in enumerate(zip(row_lines, row_lines[1:]), start=1):
                y0 = max(0, top_line + args.border_pad)
                y1 = min(image.shape[0], bottom_line - args.border_pad)
                if y1 - y0 < args.min_cell_height:
                    continue

                for col_idx, (left_line, right_line) in enumerate(zip(col_lines, col_lines[1:]), start=1):
                    x0 = max(0, left_line + args.border_pad)
                    x1 = min(image.shape[1], right_line - args.border_pad)
                    if x1 - x0 < args.min_cell_width:
                        continue

                    cx0 = min(max(x0 + args.content_inner_margin, x0), x1)
                    cx1 = max(min(x1 - args.content_inner_margin, x1), cx0)
                    cy0 = min(max(y0 + args.content_inner_margin, y0), y1)
                    cy1 = max(min(y1 - args.content_inner_margin, y1), cy0)
                    cell_mask = content_mask[cy0:cy1, cx0:cx1]
                    if cell_mask.size == 0:
                        continue

                    ink_pixels = int((cell_mask > 0).sum())
                    area = max(1, cell_mask.shape[0] * cell_mask.shape[1])
                    if ink_pixels < args.min_content_pixels:
                        continue
                    if ink_pixels / area < args.min_content_ratio:
                        continue

                    sx0 = max(0, x0 - args.crop_expand_x)
                    sx1 = min(image.shape[1], x1 + args.crop_expand_x)
                    sy0 = max(0, y0 - args.crop_expand_y)
                    sy1 = min(image.shape[0], y1 + args.crop_expand_y)

                    crop = image[sy0:sy1, sx0:sx1]
                    out_path = source_dir / f"{source_name}_r{row_idx:03d}_c{col_idx:03d}.png"
                    cv2.imwrite(str(out_path), crop)
                    writer.writerow([source, row_idx, col_idx, str(out_path), sx0, sy0, sx1, sy1, ink_pixels])
                    kept += 1

            print(
                f"grid: {Path(source).name} -> {len(row_lines) - 1} row bands, "
                f"{len(col_lines) - 1} col bands, {kept} non-empty cells"
            )


if __name__ == "__main__":
    main()
