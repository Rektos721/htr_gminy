from __future__ import annotations

import argparse
import csv
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
        "--manifest",
        type=Path,
        help="Optional training_manifest.csv — domyślnie używa wszystkich wierszy z niepustym gt.txt.",
    )
    parser.add_argument(
        "--extra-gt-dirs",
        nargs="+",
        type=Path,
        default=[],
        help="Dodatkowe katalogi z PNG+gt.txt (np. external_data/popp). Skanowane rekurencyjnie.",
    )
    parser.add_argument(
        "--max-extra-samples",
        type=int,
        default=None,
        help="Maksymalna liczba próbek z każdego extra-gt-dir (losowy wybór).",
    )
    parser.add_argument(
        "--only-ready",
        action="store_true",
        help="Jeśli podany z --manifest, używa tylko wierszy ze statusem 'ready'.",
    )
    parser.add_argument(
        "--ketos-exe",
        type=Path,
        default=Path(r"C:\Users\Nocna\AppData\Local\Programs\Python\Python312\Scripts\ketos.exe"),
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

    if args.manifest:
        manifest = args.manifest.resolve()
        if not manifest.exists():
            raise SystemExit(f"Manifest not found: {manifest}")
        with open(manifest, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        if args.only_ready:
            candidates = [r for r in rows if r.get("status") == "ready"]
            label = "ready"
        else:
            # wszystkie wiersze które mają niepusty plik gt.txt
            candidates = []
            for r in rows:
                gt = Path(r.get("manual_text_path") or "") or Path(r["image"]).with_suffix(".gt.txt")
                if not gt.exists():
                    gt = Path(r["image"]).with_suffix(".gt.txt")
                if gt.exists() and gt.read_text(encoding="utf-8").strip():
                    candidates.append(r)
            label = "z tekstem"
        if not candidates:
            raise SystemExit(f"Brak wierszy {label} w manifeście.")
        images = [Path(r["image"]) for r in candidates if Path(r["image"]).exists()]
        missing = len(candidates) - len(images)
        if missing:
            print(f"Uwaga: {missing} plików z manifestu nie istnieje na dysku.")
        print(f"Manifest: {len(candidates)} {label}, {len(images)} plików znalezionych.")
    else:
        images = sorted(gt_dir.rglob("*.png")) + sorted(gt_dir.rglob("*.jpg")) + sorted(gt_dir.rglob("*.tif"))

    if not images:
        raise SystemExit(f"No training images found.")

    for extra_dir in args.extra_gt_dirs:
        import random
        extra_dir = extra_dir.resolve()
        extra_imgs = [p for p in (
            sorted(extra_dir.rglob("*.png")) +
            sorted(extra_dir.rglob("*.jpg")) +
            sorted(extra_dir.rglob("*.tif"))
        ) if p.with_suffix(".gt.txt").exists() and p.with_suffix(".gt.txt").read_text(encoding="utf-8").strip()]
        if args.max_extra_samples and len(extra_imgs) > args.max_extra_samples:
            random.seed(42)
            extra_imgs = random.sample(extra_imgs, args.max_extra_samples)
        print(f"Extra dir {extra_dir.name}: {len(extra_imgs)} plików z tekstem")
        images += extra_imgs

    print(f"Łącznie: {len(images)} obrazów do treningu")
    output_dir.mkdir(parents=True, exist_ok=True)
    dataset_arrow.parent.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"

    print(f"Kompilacja datasetu: {len(images)} obrazów → {dataset_arrow}")
    from kraken.lib.arrow_dataset import build_binary_dataset
    build_binary_dataset(
        files=[str(p) for p in images],
        output_file=str(dataset_arrow),
        format_type="path",
        force_type="kraken_recognition_bbox",
        num_workers=0,
        skip_empty_lines=True,
        random_split=(args.partition, round(1.0 - args.partition, 4), 0.0),
    )
    print(f"Dataset skompilowany: {dataset_arrow}")

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
