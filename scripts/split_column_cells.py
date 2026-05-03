from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np

HEADER_SKIP_OVERRIDES = {
    "oborniki-028": 5,
}


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
    bridge_gap_v: int = 15,
    bridge_gap_h: int = 5,
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
        cv2.MORPH_RECT, (1, max(20, image.shape[0] // vertical_divisor))
    )
    horizontal = cv2.morphologyEx(binary, cv2.MORPH_OPEN, horizontal_kernel)
    vertical = cv2.morphologyEx(binary, cv2.MORPH_OPEN, vertical_kernel)
    if bridge_gap_v > 0:
        vertical = cv2.dilate(vertical, np.ones((bridge_gap_v, 1), np.uint8))
    if bridge_gap_h > 0:
        horizontal = cv2.dilate(horizontal, np.ones((1, bridge_gap_h), np.uint8))
    return binary, horizontal, vertical


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Splits handwritten table pages into non-empty cell crops.")
    parser.add_argument("--columns-manifest", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--adaptive-block-size", type=int, default=35)
    parser.add_argument("--adaptive-c", type=int, default=11)
    parser.add_argument("--horizontal-divisor", type=int, default=28)
    parser.add_argument("--vertical-divisor", type=int, default=50)
    parser.add_argument("--col-threshold-ratio", type=float, default=0.04)
    parser.add_argument("--row-threshold-ratio", type=float, default=0.12)
    parser.add_argument("--line-cluster-tolerance", type=int, default=5)
    parser.add_argument("--bridge-gap-v", type=int, default=15)
    parser.add_argument("--bridge-gap-h", type=int, default=5)
    parser.add_argument("--skip-first-lines", type=int, default=2)
    parser.add_argument("--min-cell-width", type=int, default=50)
    parser.add_argument("--min-cell-height", type=int, default=40)
    parser.add_argument("--min-content-pixels", type=int, default=200)
    parser.add_argument("--min-content-ratio", type=float, default=0.004)
    parser.add_argument("--border-pad", type=int, default=3)
    parser.add_argument("--content-inner-margin", type=int, default=10)
    parser.add_argument("--crop-expand-x", type=int, default=10)
    parser.add_argument("--crop-expand-y", type=int, default=6)
    parser.add_argument("--detect-max-width", type=int, default=3600)
    parser.add_argument("--min-component-area", type=int, default=36)
    parser.add_argument("--min-component-width", type=int, default=4)
    parser.add_argument("--min-component-height", type=int, default=8)
    return parser


def detect_row_lines_rescaled(image: np.ndarray, args: argparse.Namespace) -> list[int]:
    detect_image = image
    scale = 1.0
    if args.detect_max_width > 0 and image.shape[1] > args.detect_max_width:
        scale = args.detect_max_width / image.shape[1]
        detect_image = cv2.resize(
            image,
            (int(round(image.shape[1] * scale)), int(round(image.shape[0] * scale))),
            interpolation=cv2.INTER_AREA,
        )

    _, horizontal_small, _ = build_masks(
        image=detect_image,
        adaptive_block_size=args.adaptive_block_size,
        adaptive_c=args.adaptive_c,
        horizontal_divisor=args.horizontal_divisor,
        vertical_divisor=args.vertical_divisor,
        bridge_gap_v=args.bridge_gap_v,
        bridge_gap_h=args.bridge_gap_h,
    )
    tolerance = max(4, int(round(args.line_cluster_tolerance * scale))) if scale != 1.0 else args.line_cluster_tolerance
    row_lines_small = detect_lines(
        mask=horizontal_small,
        axis=1,
        threshold_ratio=args.row_threshold_ratio,
        tolerance=tolerance,
    )
    row_lines = [int(round(y / scale)) for y in row_lines_small]
    return cluster_positions(np.array(row_lines, dtype=int), tolerance=max(args.line_cluster_tolerance, 12))


def detect_col_lines_rescaled(image: np.ndarray, args: argparse.Namespace) -> list[int]:
    detect_image = image
    scale = 1.0
    if args.detect_max_width > 0 and image.shape[1] > args.detect_max_width:
        scale = args.detect_max_width / image.shape[1]
        detect_image = cv2.resize(
            image,
            (int(round(image.shape[1] * scale)), int(round(image.shape[0] * scale))),
            interpolation=cv2.INTER_AREA,
        )

    _, _, vertical_small = build_masks(
        image=detect_image,
        adaptive_block_size=args.adaptive_block_size,
        adaptive_c=args.adaptive_c,
        horizontal_divisor=args.horizontal_divisor,
        vertical_divisor=args.vertical_divisor,
        bridge_gap_v=args.bridge_gap_v,
        bridge_gap_h=args.bridge_gap_h,
    )
    tolerance = max(4, int(round(args.line_cluster_tolerance * scale))) if scale != 1.0 else args.line_cluster_tolerance
    col_lines_small = detect_lines(
        mask=vertical_small,
        axis=0,
        threshold_ratio=args.col_threshold_ratio,
        tolerance=tolerance,
    )
    col_lines = [int(round(x / scale)) for x in col_lines_small]
    col_lines = cluster_positions(np.array(col_lines, dtype=int), tolerance=max(args.line_cluster_tolerance, 12))
    col_lines = [x for x in col_lines if 0 <= x <= image.shape[1]]
    if not col_lines or col_lines[0] > 20:
        col_lines = [0] + col_lines
    if col_lines[-1] < image.shape[1] - 20:
        col_lines.append(image.shape[1] - 1)
    return col_lines


def has_textlike_content(
    cell_mask: np.ndarray,
    min_content_pixels: int,
    min_content_ratio: float,
    min_component_area: int,
    min_component_width: int,
    min_component_height: int,
) -> tuple[bool, int]:
    if cell_mask.size == 0:
        return False, 0

    _, _, stats, _ = cv2.connectedComponentsWithStats((cell_mask > 0).astype(np.uint8), connectivity=8)
    kept_pixels = 0
    kept_components = 0
    min_x = None
    min_y = None
    max_x = None
    max_y = None
    for label_idx in range(1, stats.shape[0]):
        x, y, w, h, area = stats[label_idx]
        if area < min_component_area:
            continue
        if w < min_component_width or h < min_component_height:
            continue
        if w <= 8 and h >= w * 6:
            continue
        if h <= 8 and w >= h * 10:
            continue
        kept_pixels += int(area)
        kept_components += 1
        min_x = x if min_x is None else min(min_x, x)
        min_y = y if min_y is None else min(min_y, y)
        max_x = x + w if max_x is None else max(max_x, x + w)
        max_y = y + h if max_y is None else max(max_y, y + h)

    area = max(1, cell_mask.shape[0] * cell_mask.shape[1])
    if kept_components == 0:
        return False, kept_pixels
    bbox_width = max_x - min_x if min_x is not None and max_x is not None else 0
    bbox_height = max_y - min_y if min_y is not None and max_y is not None else 0
    if bbox_width < 12 and bbox_height < 20:
        return False, kept_pixels
    if bbox_width < 8 or bbox_height < 10:
        return False, kept_pixels
    if kept_pixels < min_content_pixels:
        return False, kept_pixels
    if kept_pixels / area < min_content_ratio:
        return False, kept_pixels
    return True, kept_pixels


def main() -> None:
    args = build_parser().parse_args()
    manifest_path = args.columns_manifest.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    with manifest_path.open("r", encoding="utf-8", newline="") as handle:
        manifest_rows = list(csv.DictReader(handle))

    by_source: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in manifest_rows:
        by_source[row["source"]].append(row)

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

        for source in sorted(by_source):
            image = cv2.imread(source, cv2.IMREAD_GRAYSCALE)
            if image is None:
                raise SystemExit(f"Failed to read image: {source}")

            col_lines = detect_col_lines_rescaled(image, args)
            row_lines = detect_row_lines_rescaled(image, args)
            if len(row_lines) <= args.skip_first_lines + 1 or len(col_lines) < 2:
                print(f"grid: {Path(source).name} -> insufficient lines ({len(row_lines)} rows, {len(col_lines)} cols)")
                continue

            extra_skip = HEADER_SKIP_OVERRIDES.get(Path(source).stem, args.skip_first_lines)
            row_lines = row_lines[extra_skip:]

            binary, horizontal, vertical = build_masks(
                image=image,
                adaptive_block_size=args.adaptive_block_size,
                adaptive_c=args.adaptive_c,
                horizontal_divisor=args.horizontal_divisor,
                vertical_divisor=args.vertical_divisor,
                bridge_gap_v=args.bridge_gap_v,
                bridge_gap_h=args.bridge_gap_h,
            )
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

                    has_content, ink_pixels = has_textlike_content(
                        cell_mask=cell_mask,
                        min_content_pixels=args.min_content_pixels,
                        min_content_ratio=args.min_content_ratio,
                        min_component_area=args.min_component_area,
                        min_component_width=args.min_component_width,
                        min_component_height=args.min_component_height,
                    )
                    if not has_content:
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
