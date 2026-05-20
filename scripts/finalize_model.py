"""
Po zakończeniu treningu: wybiera najlepszy checkpoint i zapisuje jako .mlmodel
Użycie: python scripts/finalize_model.py --model-dir outputs/model_v2 --out models/htr_wysoka_v2.mlmodel
"""
from __future__ import annotations
import argparse
import re
from pathlib import Path


def best_checkpoint(model_dir: Path) -> Path:
    ckpts = list(model_dir.glob("checkpoint_*.ckpt"))
    if not ckpts:
        raise SystemExit(f"Brak checkpointów w {model_dir}")

    def score(p: Path) -> float:
        m = re.search(r"checkpoint_\d+-(\d+\.\d+)\.ckpt", p.name)
        return float(m.group(1)) if m else 0.0

    best = max(ckpts, key=score)
    print(f"Najlepszy checkpoint: {best.name}  (accuracy {score(best):.4f})")
    return best


def convert(ckpt: Path, out: Path) -> None:
    from kraken.train import VGSLRecognitionModel
    print(f"Ładuję {ckpt.name} ...")
    m = VGSLRecognitionModel.load_from_checkpoint(str(ckpt))
    out.parent.mkdir(parents=True, exist_ok=True)
    m.net.save_model(str(out))
    print(f"Model zapisany: {out}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--model-dir", type=Path, default=Path("outputs/model_v2"))
    p.add_argument("--out", type=Path, default=Path("models/htr_wysoka_v2.mlmodel"))
    args = p.parse_args()

    ckpt = best_checkpoint(args.model_dir)
    convert(ckpt, args.out)


if __name__ == "__main__":
    main()
