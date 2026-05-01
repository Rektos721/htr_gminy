from __future__ import annotations

import argparse
import csv
import os
import subprocess
import sys
from pathlib import Path


SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp"}


def iter_images(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTS
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Runs Kraken page segmentation + OCR on handwritten pages.")
    parser.add_argument("--input-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--model-path", required=True, type=Path)
    parser.add_argument(
        "--kraken-exe",
        type=Path,
        default=Path(r"C:\Users\Nocna\htr-env\Scripts\kraken.exe"),
    )
    parser.add_argument("--batch-size", type=int, default=1)
    return parser


def run_page_ocr(kraken_exe: Path, model_path: Path, src: Path, dst: Path, batch_size: int) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    command = [
        str(kraken_exe),
        "-i",
        str(src),
        str(dst),
        "binarize",
        "segment",
        "ocr",
        "-m",
        str(model_path),
        "-B",
        str(batch_size),
        "--num-line-workers",
        "0",
    ]
    return subprocess.run(command, capture_output=True, text=True, env=env)


def main() -> None:
    args = build_parser().parse_args()
    input_dir = args.input_dir.resolve()
    output_dir = args.output_dir.resolve()
    model_path = args.model_path.resolve()
    kraken_exe = args.kraken_exe.resolve()

    if not kraken_exe.exists():
        raise SystemExit(f"Kraken executable not found: {kraken_exe}")
    if not model_path.exists():
        raise SystemExit(f"Kraken model not found: {model_path}")

    images = iter_images(input_dir)
    if not images:
        raise SystemExit(f"No supported images found in {input_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "kraken_page_results.csv"

    with manifest_path.open("w", newline="", encoding="utf-8") as manifest_file:
        writer = csv.writer(manifest_file)
        writer.writerow(["source", "text_file", "status", "stderr"])

        for src in images:
            relative = src.relative_to(input_dir)
            dst = output_dir / relative.with_suffix(".txt")
            dst.parent.mkdir(parents=True, exist_ok=True)

            result = run_page_ocr(
                kraken_exe=kraken_exe,
                model_path=model_path,
                src=src,
                dst=dst,
                batch_size=args.batch_size,
            )

            status = "ok" if result.returncode == 0 else "error"
            stderr = (result.stderr or "").strip().replace("\n", " | ")
            writer.writerow([str(src), str(dst), status, stderr])
            print(f"{status}: {src.name}")

            if result.returncode != 0:
                print(stderr, file=sys.stderr)


if __name__ == "__main__":
    main()
