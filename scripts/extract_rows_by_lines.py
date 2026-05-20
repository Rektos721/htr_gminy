from __future__ import annotations

import argparse
import csv
from pathlib import Path

import cv2
import numpy as np

SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}


def detect_horizontal_lines(image: np.ndarray, divisor: int = 60, threshold_ratio: float = 0.3, tolerance: int = 8) -> list[int]:
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(30, image.shape[1] // divisor), 1))
    binary = cv2.adaptiveThreshold(image, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 35, 11)
    horizontal = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)

    strength = (horizontal > 0).sum(axis=1)
    threshold = int(image.shape[1] * threshold_ratio)
    hits = np.where(strength >= threshold)[0]

    if len(hits) == 0:
        return []

    clusters: list[list[int]] = [[int(hits[0])]]
    for y in hits[1:]:
        if int(y) - clusters[-1][-1] <= tolerance:
            clusters[-1].append(int(y))
        else:
            clusters.append([int(y)])
    return [int(round(sum(c) / len(c))) for c in clusters]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Wycina wiersze tabeli na podstawie wykrytych linii poziomych.")
    parser.add_argument("--input-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--skip-first", type=int, default=1, help="Ile pierwszych wierszy pominac (naglowek)")
    parser.add_argument("--min-row-height", type=int, default=40)
    parser.add_argument("--pad", type=int, default=4)
    parser.add_argument("--divisor", type=int, default=60)
    parser.add_argument("--threshold-ratio", type=float, default=0.3)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    input_dir = args.input_dir.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    images = sorted(p for p in input_dir.iterdir() if p.suffix.lower() in SUPPORTED_EXTS)
    if not images:
        raise SystemExit(f"Brak obrazow w {input_dir}")

    manifest_path = output_dir / "rows_manifest.csv"
    total_rows = 0

    with manifest_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["source", "row_image", "row_index", "top", "bottom"])

        for img_path in images:
            image = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
            if image is None:
                print(f"SKIP: {img_path.name}")
                continue

            lines = detect_horizontal_lines(image, divisor=args.divisor, threshold_ratio=args.threshold_ratio)

            if len(lines) < 2:
                print(f"rows: {img_path.name} -> za malo linii ({len(lines)}), pomijam")
                continue

            lines = lines[args.skip_first:]

            row_dir = output_dir / img_path.stem
            row_dir.mkdir(exist_ok=True)

            row_idx = 0
            for top, bottom in zip(lines, lines[1:]):
                height = bottom - top
                if height < args.min_row_height:
                    continue
                row_idx += 1
                y0 = max(0, top - args.pad)
                y1 = min(image.shape[0], bottom + args.pad)
                crop = image[y0:y1, :]
                out_path = row_dir / f"{img_path.stem}_row_{row_idx:03d}.png"
                cv2.imwrite(str(out_path), crop)
                writer.writerow([str(img_path), str(out_path), row_idx, y0, y1])

            total_rows += row_idx
            print(f"rows: {img_path.name} -> {len(lines)} linii, {row_idx} wierszy danych")

    print(f"\nRazem: {total_rows} wierszy -> {manifest_path}")


if __name__ == "__main__":
    main()
