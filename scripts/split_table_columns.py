from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from PIL import Image, ImageOps


SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp"}

PRESETS = {
    "wz_like": [
        {"name": "lp", "start": 0.00, "end": 0.06},
        {"name": "znak", "start": 0.06, "end": 0.20},
        {"name": "opis", "start": 0.20, "end": 0.56},
        {"name": "lokalizacja", "start": 0.56, "end": 0.72},
        {"name": "wnioskodawca", "start": 0.72, "end": 0.88},
        {"name": "decyzja", "start": 0.88, "end": 1.00},
    ]
}


def iter_images(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTS
    )


def load_columns(preset: str | None, config_path: Path | None) -> list[dict]:
    if config_path:
        with config_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data["columns"]
    if preset:
        try:
            return PRESETS[preset]
        except KeyError as exc:
            raise SystemExit(f"Unknown preset: {preset}") from exc
    raise SystemExit("Pass either --preset or --config.")


def crop_columns(
    src: Path,
    dst_dir: Path,
    columns: list[dict],
    left_trim: float,
    right_trim: float,
    top_trim: float,
    bottom_trim: float,
) -> list[tuple[str, str, str, int, int, int, int]]:
    image = Image.open(src).convert("L")
    image = ImageOps.exif_transpose(image)
    width, height = image.size

    left = int(width * left_trim)
    right = int(width * (1.0 - right_trim))
    top = int(height * top_trim)
    bottom = int(height * (1.0 - bottom_trim))
    table = image.crop((left, top, right, bottom))

    rows: list[tuple[str, str, str, int, int, int, int]] = []
    base_dir = dst_dir / src.stem
    base_dir.mkdir(parents=True, exist_ok=True)

    for idx, column in enumerate(columns, start=1):
        start = max(0.0, min(1.0, float(column["start"])))
        end = max(0.0, min(1.0, float(column["end"])))
        name = str(column["name"])
        x0 = int(table.width * start)
        x1 = int(table.width * end)
        crop = table.crop((x0, 0, x1, table.height))
        out_path = base_dir / f"{src.stem}_col_{idx:02d}_{name}.png"
        crop.save(out_path)
        rows.append((str(src), str(out_path), name, x0, 0, x1, table.height))
    return rows


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Splits stable table layouts into column crops.")
    parser.add_argument("--input-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--preset", default=None)
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--left-trim", type=float, default=0.02)
    parser.add_argument("--right-trim", type=float, default=0.02)
    parser.add_argument("--top-trim", type=float, default=0.04)
    parser.add_argument("--bottom-trim", type=float, default=0.02)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    input_dir = args.input_dir.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    columns = load_columns(args.preset, args.config)

    images = iter_images(input_dir)
    if not images:
        raise SystemExit(f"No supported images found in {input_dir}")

    manifest_path = output_dir / "columns_manifest.csv"
    with manifest_path.open("w", newline="", encoding="utf-8") as manifest_file:
        writer = csv.writer(manifest_file)
        writer.writerow(["source", "column_image", "column_name", "x0", "y0", "x1", "y1"])
        for src in images:
            meta = crop_columns(
                src=src,
                dst_dir=output_dir,
                columns=columns,
                left_trim=args.left_trim,
                right_trim=args.right_trim,
                top_trim=args.top_trim,
                bottom_trim=args.bottom_trim,
            )
            for row in meta:
                writer.writerow(row)
            print(f"columns: {src.name} -> {len(meta)}")


if __name__ == "__main__":
    main()
