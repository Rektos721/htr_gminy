"""preprocess_handwritten.py — przygotowuje skany tabel do HTR.

Kolejność operacji:
  1. Grayscale + EXIF transpose
  2. Autocontrast
  3. Upscale (opcjonalnie)
  4. Median filter (odszumowanie)
  5. Deskew — prostuje pochylony skan (opcjonalnie, --deskew)
  6. Unsharp mask (opcjonalnie)
  7. Threshold binaryzacja (opcjonalnie)

Użycie:
    python scripts/preprocess_handwritten.py \\
        --input-dir  outputs/pages/rejestr/ \\
        --output-dir outputs/prepared/rejestr/ \\
        --deskew

    # Z binaryzacją i deskew:
    python scripts/preprocess_handwritten.py \\
        --input-dir  outputs/pages/ \\
        --output-dir outputs/prepared/ \\
        --deskew --threshold 160
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageFilter, ImageOps


SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp"}


def iter_images(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTS
    )


# ---------------------------------------------------------------------------
# Deskew
# ---------------------------------------------------------------------------

def detect_skew_angle(pil_gray: Image.Image, max_angle: float) -> float:
    """Wykrywa kąt pochylenia skanu metodą minAreaRect na pikselach atramentu.

    Zwraca kąt w stopniach (dodatni = obrót w lewo, ujemny = obrót w prawo).
    Jeśli wykryty kąt przekracza max_angle — zwraca 0.0 (brak korekcji).
    """
    arr = np.array(pil_gray, dtype=np.uint8)

    # Binaryzacja Otsu (odwrócona: atrament = 255)
    _, binary = cv2.threshold(arr, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # Współrzędne pikseli atramentu
    coords = np.column_stack(np.where(binary > 0))
    if len(coords) < 100:
        return 0.0

    # minAreaRect zwraca (center, (w, h), angle)
    rect = cv2.minAreaRect(coords)
    angle = rect[-1]  # zakres: [-90, 0)

    # Konwersja do kąta pochylenia od poziomej
    if angle < -45:
        angle = 90 + angle   # np. -80 → +10
    else:
        angle = angle        # np. -5 → -5

    # Ignoruj duże kąty — to prawdopodobnie błąd detekcji (nie pochylenie)
    if abs(angle) > max_angle:
        return 0.0

    return angle


def deskew(pil_image: Image.Image, max_angle: float) -> tuple[Image.Image, float]:
    """Prostuje pochylony obraz. Zwraca (wyprostowany_obraz, wykryty_kąt)."""
    gray = pil_image.convert("L")
    angle = detect_skew_angle(gray, max_angle)

    if abs(angle) < 0.1:
        return pil_image, angle

    # Obrót: PIL rotate jest przeciwny do kąta pochylenia
    rotated = pil_image.rotate(
        -angle,
        resample=Image.Resampling.BICUBIC,
        expand=True,
        fillcolor=255,
    )
    return rotated, angle


# ---------------------------------------------------------------------------
# Główne przetwarzanie
# ---------------------------------------------------------------------------

def prepare_image(
    src: Path,
    dst: Path,
    upscale: float,
    threshold: int | None,
    sharpen: bool,
    do_deskew: bool,
    deskew_max_angle: float,
) -> tuple[int, int, float]:
    """Przetwarza jeden obraz. Zwraca (width, height, kąt_deskew)."""
    image = Image.open(src).convert("L")
    image = ImageOps.exif_transpose(image)
    image = ImageOps.autocontrast(image)

    if upscale != 1.0:
        width  = max(1, int(image.width  * upscale))
        height = max(1, int(image.height * upscale))
        image  = image.resize((width, height), Image.Resampling.LANCZOS)

    image = image.filter(ImageFilter.MedianFilter(size=3))

    skew_angle = 0.0
    if do_deskew:
        image, skew_angle = deskew(image, deskew_max_angle)

    if sharpen:
        image = image.filter(
            ImageFilter.UnsharpMask(radius=1.4, percent=180, threshold=3)
        )

    if threshold is not None:
        image = image.point(lambda px: 255 if px >= threshold else 0)

    dst.parent.mkdir(parents=True, exist_ok=True)
    image.save(dst)
    return image.width, image.height, skew_angle


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Przygotowuje skany tabel ręcznie pisanych do HTR."
    )
    p.add_argument("--input-dir",  required=True, type=Path,
                   help="Katalog ze skanami (PNG/JPG/TIF).")
    p.add_argument("--output-dir", required=True, type=Path,
                   help="Katalog wyjściowy.")
    p.add_argument("--upscale",    type=float, default=1.5,
                   help="Współczynnik powiększenia (domyślnie 1.5). Użyj 1.0 żeby wyłączyć.")
    p.add_argument("--threshold",  type=int, default=None,
                   help="Próg binaryzacji 0–255. Brak = bez binaryzacji.")
    p.add_argument("--no-sharpen", action="store_true",
                   help="Wyłącz unsharp mask.")
    p.add_argument("--deskew",     action="store_true",
                   help="Prostuj pochylone skany (zalecane dla skanów ręcznych).")
    p.add_argument("--deskew-max-angle", type=float, default=15.0,
                   help="Maksymalny kąt korekcji w stopniach (domyślnie 15). "
                        "Większe kąty są ignorowane — prawdopodobnie błąd detekcji.")
    return p


def main() -> None:
    args = build_parser().parse_args()
    input_dir:  Path = args.input_dir.resolve()
    output_dir: Path = args.output_dir.resolve()

    images = iter_images(input_dir)
    if not images:
        raise SystemExit(f"Brak obsługiwanych obrazów w {input_dir}")

    manifest_path = output_dir / "manifest.csv"
    output_dir.mkdir(parents=True, exist_ok=True)

    with manifest_path.open("w", newline="", encoding="utf-8") as manifest_file:
        writer = csv.writer(manifest_file)
        writer.writerow(["source", "prepared", "width", "height", "skew_angle"])

        for src in images:
            relative = src.relative_to(input_dir)
            dst = output_dir / relative.with_suffix(".png")

            width, height, skew_angle = prepare_image(
                src=src,
                dst=dst,
                upscale=args.upscale,
                threshold=args.threshold,
                sharpen=not args.no_sharpen,
                do_deskew=args.deskew,
                deskew_max_angle=args.deskew_max_angle,
            )

            skew_info = f"  skew={skew_angle:+.2f}°" if args.deskew else ""
            print(f"prepared: {src.name} → {dst.name} ({width}×{height}){skew_info}")
            writer.writerow([str(src), str(dst), width, height, f"{skew_angle:.2f}"])


if __name__ == "__main__":
    main()
