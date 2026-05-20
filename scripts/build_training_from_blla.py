from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}


def segment_page(img_path: Path, seg_path: Path) -> None:
    cmd = ["kraken", "-i", str(img_path), str(seg_path), "segment", "-bl"]
    env = {"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    import os
    full_env = os.environ.copy()
    full_env.update(env)
    result = subprocess.run(cmd, env=full_env, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(f"kraken segment failed: {result.stderr.decode('utf-8', errors='replace')}")


def load_baselines(seg_path: Path) -> list[dict]:
    with seg_path.open(encoding="utf-8") as f:
        data = json.load(f)
    return data.get("lines", [])


def cluster_by_y(lines: list[dict], gap: int = 50) -> list[list[dict]]:
    if not lines:
        return []
    def midpoint_y(line: dict) -> float:
        bl = line.get("baseline", [])
        if not bl:
            return 0
        return sum(pt[1] for pt in bl) / len(bl)

    sorted_lines = sorted(lines, key=midpoint_y)
    clusters: list[list[dict]] = [[sorted_lines[0]]]
    for line in sorted_lines[1:]:
        my = midpoint_y(line)
        prev_y = midpoint_y(clusters[-1][-1])
        if my - prev_y <= gap:
            clusters[-1].append(line)
        else:
            clusters.append([line])
    return clusters


def row_crop_y(cluster: list[dict], image_h: int, pad: int = 8) -> tuple[int, int]:
    all_pts = [pt for line in cluster for pt in line.get("boundary", line.get("baseline", []))]
    if not all_pts:
        return 0, image_h
    ys = [pt[1] for pt in all_pts]
    return max(0, min(ys) - pad), min(image_h, max(ys) + pad)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Segmentuje strony przez blla, wycina wiersze, laczy z OCR Gemini."
    )
    parser.add_argument("--input-dir", required=True, type=Path)
    parser.add_argument("--ocr-csv", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--seg-dir", type=Path, default=None)
    parser.add_argument("--row-gap", type=int, default=50)
    parser.add_argument("--pad", type=int, default=8)
    parser.add_argument("--skip-first-rows", type=int, default=1, help="Pomin naglowek (1=tak)")
    return parser


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    args = build_parser().parse_args()

    input_dir = args.input_dir.resolve()
    output_dir = args.output_dir.resolve()
    seg_dir = (args.seg_dir or output_dir / "segments").resolve()
    gt_dir = (output_dir / "ground-truth").resolve()
    gt_dir.mkdir(parents=True, exist_ok=True)
    seg_dir.mkdir(parents=True, exist_ok=True)

    # Zaladuj OCR Gemini: klucz = stem strony, wartosc = {row_nr: tekst_wiersza}
    ocr_by_page: dict[str, dict[int, str]] = {}
    with args.ocr_csv.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            stem = Path(row["source"]).stem
            try:
                r = int(row["row"])
                cols = json.loads(row["cols_json"])
                text = " | ".join(str(c).strip() for c in cols if str(c).strip())
                ocr_by_page.setdefault(stem, {})[r] = text
            except (ValueError, json.JSONDecodeError):
                pass

    images = sorted(p for p in input_dir.iterdir() if p.suffix.lower() in SUPPORTED_EXTS)
    manifest: list[dict] = []
    total_pairs = 0

    for img_path in images:
        seg_path = seg_dir / f"{img_path.stem}.json"
        print(f"\nSegmentuje: {img_path.name}", flush=True)

        if not seg_path.exists():
            try:
                segment_page(img_path, seg_path)
            except RuntimeError as e:
                print(f"  BLAD: {e}", flush=True)
                continue

        lines = load_baselines(seg_path)
        if not lines:
            print(f"  Brak linii w segmentacji", flush=True)
            continue

        clusters = cluster_by_y(lines, gap=args.row_gap)
        print(f"  Segmentow: {len(lines)}, wierszy po grupowaniu: {len(clusters)}", flush=True)

        if args.skip_first_rows > 0:
            clusters = clusters[args.skip_first_rows:]

        image = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
        if image is None:
            print(f"  Nie mozna odczytac obrazu", flush=True)
            continue

        page_ocr = ocr_by_page.get(img_path.stem, {})
        row_dir = gt_dir / img_path.stem
        row_dir.mkdir(exist_ok=True)

        matched = 0
        for idx, cluster in enumerate(clusters, start=1):
            y0, y1 = row_crop_y(cluster, image.shape[0], pad=args.pad)
            if y1 - y0 < 20:
                continue

            crop = image[y0:y1, :]
            out_img = row_dir / f"{img_path.stem}_row_{idx:03d}.png"
            cv2.imwrite(str(out_img), crop)

            text = page_ocr.get(idx, "")
            out_txt = row_dir / f"{img_path.stem}_row_{idx:03d}.gt.txt"
            out_txt.write_text(text, encoding="utf-8")

            manifest.append({
                "image": str(out_img),
                "gt_text": text,
                "source": img_path.name,
                "row": idx,
                "has_text": bool(text),
            })
            if text:
                matched += 1

        total_pairs += matched
        print(f"  Wierszy: {len(clusters)}, z tekstem OCR: {matched}", flush=True)

    manifest_path = output_dir / "training_manifest.csv"
    with manifest_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["image", "gt_text", "source", "row", "has_text"])
        writer.writeheader()
        writer.writerows(manifest)

    print(f"\nGotowe: {total_pairs} par obraz+tekst -> {manifest_path}")


if __name__ == "__main__":
    main()
