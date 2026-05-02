from __future__ import annotations

import argparse
import csv
import os
import subprocess
import tempfile
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fills ocr_guess in a review manifest using a Kraken model.")
    parser.add_argument("--review-manifest", required=True, type=Path)
    parser.add_argument("--model-path", required=True, type=Path)
    parser.add_argument(
        "--kraken-exe",
        type=Path,
        default=Path(r"C:\Users\Nocna\htr-env\Scripts\kraken.exe"),
    )
    parser.add_argument("--output-manifest", type=Path, default=None)
    parser.add_argument("--only-empty", action="store_true")
    parser.add_argument("--only-status", default="todo")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--save-every", type=int, default=10)
    return parser


def run_ocr(kraken_exe: Path, model_path: Path, image_path: Path) -> str:
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"

    with tempfile.TemporaryDirectory() as tmp_dir:
        dst = Path(tmp_dir) / f"{image_path.stem}.txt"
        command = [
            str(kraken_exe),
            "-i",
            str(image_path),
            str(dst),
            "binarize",
            "ocr",
            "-m",
            str(model_path),
            "-s",
            "-B",
            "1",
            "--num-line-workers",
            "0",
        ]
        result = subprocess.run(command, capture_output=True, text=True, env=env)
        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            raise RuntimeError(f"{image_path.name}: {stderr}")
        return dst.read_text(encoding="utf-8", errors="ignore").strip()


def write_manifest(output_manifest: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    output_manifest.parent.mkdir(parents=True, exist_ok=True)
    with output_manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = build_parser().parse_args()
    review_manifest = args.review_manifest.resolve()
    output_manifest = (args.output_manifest or review_manifest).resolve()
    model_path = args.model_path.resolve()
    kraken_exe = args.kraken_exe.resolve()

    if not review_manifest.exists():
        raise SystemExit(f"Review manifest not found: {review_manifest}")
    if not model_path.exists():
        raise SystemExit(f"Kraken model not found: {model_path}")
    if not kraken_exe.exists():
        raise SystemExit(f"Kraken executable not found: {kraken_exe}")

    with review_manifest.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
        fieldnames = list(rows[0].keys()) if rows else []

    updated = 0
    skipped = 0
    failed = 0
    processed = 0
    save_every = max(args.save_every, 1)

    for row in rows:
        image_path = Path(row["image"])
        if not image_path.exists():
            skipped += 1
            continue

        status = (row.get("status") or "").strip()
        if args.only_status and status != args.only_status:
            skipped += 1
            continue

        if args.only_empty and (row.get("ocr_guess") or "").strip():
            skipped += 1
            continue

        if args.limit and processed >= args.limit:
            break

        try:
            row["ocr_guess"] = run_ocr(kraken_exe, model_path, image_path)
            updated += 1
            processed += 1
            print(f"ok: {image_path.name}")
            if updated % save_every == 0:
                write_manifest(output_manifest, fieldnames, rows)
                print(f"checkpoint: updated={updated}")
        except RuntimeError as exc:
            failed += 1
            processed += 1
            print(f"error: {exc}")

    write_manifest(output_manifest, fieldnames, rows)

    print(f"updated={updated} skipped={skipped} failed={failed}")
    print(output_manifest)


if __name__ == "__main__":
    main()
