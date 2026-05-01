from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Runs Ketos fine-tuning from path-format ground truth.")
    parser.add_argument("--ground-truth-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--base-model", required=True, type=Path)
    parser.add_argument(
        "--ketos-exe",
        type=Path,
        default=Path(r"C:\Users\Nocna\htr-env\Scripts\ketos.exe"),
    )
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--partition", type=float, default=0.9)
    parser.add_argument("--learning-rate", type=float, default=0.0005)
    parser.add_argument("--resize", default="union")
    parser.add_argument("--device", default="cpu")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    gt_dir = args.ground_truth_dir.resolve()
    output_dir = args.output_dir.resolve()
    base_model = args.base_model.resolve()
    ketos_exe = args.ketos_exe.resolve()

    if not ketos_exe.exists():
        raise SystemExit(f"Ketos executable not found: {ketos_exe}")
    if not gt_dir.exists():
        raise SystemExit(f"Ground truth dir not found: {gt_dir}")
    if not base_model.exists():
        raise SystemExit(f"Base model not found: {base_model}")

    images = sorted(gt_dir.glob("*.png")) + sorted(gt_dir.glob("*.jpg")) + sorted(gt_dir.glob("*.tif"))
    if not images:
        raise SystemExit(f"No training images found in {gt_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"

    command = [
        str(ketos_exe),
        "-d",
        args.device,
        "train",
        "-f",
        "path",
        "-i",
        str(base_model),
        "--resize",
        args.resize,
        "-o",
        str(output_dir),
        "-N",
        str(args.epochs),
        "-B",
        str(args.batch_size),
        "-p",
        str(args.partition),
        "-r",
        str(args.learning_rate),
        str(gt_dir),
    ]

    print("running:", " ".join(command))
    result = subprocess.run(command, env=env)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
