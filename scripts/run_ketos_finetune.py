from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compiles a path-format dataset and runs Kraken/Ketos fine-tuning."
    )
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
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument(
        "--dataset-arrow",
        type=Path,
        help="Optional path for the compiled binary dataset. Defaults to <output-dir>\\dataset.arrow.",
    )
    parser.add_argument(
        "--compile-only",
        action="store_true",
        help="Only compile the binary dataset and skip training.",
    )
    return parser


def run(command: list[str], env: dict[str, str]) -> None:
    print("running:", " ".join(command))
    result = subprocess.run(command, env=env)
    if result.returncode:
        raise SystemExit(result.returncode)


def main() -> None:
    args = build_parser().parse_args()
    gt_dir = args.ground_truth_dir.resolve()
    output_dir = args.output_dir.resolve()
    base_model = args.base_model.resolve()
    ketos_exe = args.ketos_exe.resolve()
    dataset_arrow = (args.dataset_arrow or (output_dir / "dataset.arrow")).resolve()

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
    dataset_arrow.parent.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"

    compile_command = [
        str(ketos_exe),
        "-v",
        "compile",
        "-f",
        "path",
        "--force-type",
        "bbox",
        "-o",
        str(dataset_arrow),
    ]
    compile_command.extend(str(path) for path in images)
    run(compile_command, env)

    if args.compile_only:
        print(f"compiled dataset: {dataset_arrow}")
        return

    train_command = [
        str(ketos_exe),
        "-v",
        "--workers",
        str(args.workers),
        "-d",
        args.device,
        "train",
        "-f",
        "binary",
        "-i",
        str(base_model),
        "--resize",
        args.resize,
        "-o",
        str(output_dir),
        "-q",
        "fixed",
        "-N",
        str(args.epochs),
        "-B",
        str(args.batch_size),
        "-p",
        str(args.partition),
        "-r",
        str(args.learning_rate),
        str(dataset_arrow),
    ]
    run(train_command, env)


if __name__ == "__main__":
    main()
