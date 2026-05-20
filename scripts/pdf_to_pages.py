"""pdf_to_pages.py — konwertuje PDF do PNG (jedna strona = jeden plik).

Obsługuje:
- wielostronicowe PDF-y
- obrót z metadanych PDF (stosowany automatycznie przez pymupdf)
- wymuszony obrót o 180° (--rotate-180)
- auto-detekcję obrotu 180° na podstawie rozkładu atramentu (--auto-rotate)
- usuwanie kratki z papieru milimetrowego/kratowego (--remove-grid)

Użycie:
    python scripts/pdf_to_pages.py --input rejestry/ --output-dir outputs/pages/
    python scripts/pdf_to_pages.py --input dok.pdf  --output-dir outputs/pages/ --rotate-180
    python scripts/pdf_to_pages.py --input dok.pdf  --output-dir outputs/pages/ --auto-rotate
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import fitz  # pymupdf
import cv2
import numpy as np


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def pdf_to_pixmaps(pdf_path: Path, dpi: int) -> list[tuple[int, np.ndarray]]:
    """Zwraca listę (numer_strony_1based, obraz_BGR)."""
    doc = fitz.open(str(pdf_path))
    scale = dpi / 72.0
    mat = fitz.Matrix(scale, scale)
    pages: list[tuple[int, np.ndarray]] = []
    for i, page in enumerate(doc, start=1):
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
        img_bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        pages.append((i, img_bgr))
    doc.close()
    return pages


def detect_upside_down(img_bgr: np.ndarray) -> bool:
    """Heurystyka: jeśli dolna ćwiartka ma wyraźnie więcej atramentu niż górna → prawdopodobnie odwrócony.

    W rejestrach WZ nagłówek i pierwsze wiersze są na górze → górna część
    powinna mieć gęstość atramentu >= dolnej. Jeśli odwrotnie — obracamy.
    """
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    h = gray.shape[0]
    quarter = max(1, h // 4)

    top    = gray[:quarter, :]
    bottom = gray[h - quarter:, :]

    # Atrament = ciemne piksele (poniżej progu)
    ink_top    = np.sum(top    < 128) / top.size
    ink_bottom = np.sum(bottom < 128) / bottom.size

    # Jeśli dół ma >40% więcej atramentu niż góra → odwrócony
    return ink_bottom > ink_top * 1.4


def remove_grid(img_bgr: np.ndarray) -> np.ndarray:
    """Usuwa siatkę kratki (poziome i pionowe linie) operacjami morfologicznymi OpenCV.

    Działa najlepiej na papierze w kratkę z regularną siatką.
    Nie usuwa linii tabeli (są grubsze/nieregularne).
    """
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    thresh = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV,
        blockSize=15, C=10,
    )

    # Wykryj poziome linie kratki (długie, cienkie)
    h_kernel_len = max(30, gray.shape[1] // 40)
    h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (h_kernel_len, 1))
    h_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, h_kernel, iterations=1)

    # Wykryj pionowe linie kratki
    v_kernel_len = max(30, gray.shape[0] // 40)
    v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, v_kernel_len))
    v_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, v_kernel, iterations=1)

    # Maska kratki = suma linii, lekko rozszerzona żeby zakryć całą linię
    grid_mask = cv2.bitwise_or(h_lines, v_lines)
    dilate_k = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    grid_mask = cv2.dilate(grid_mask, dilate_k, iterations=1)

    # Zamaluj siatkę na biało
    result = img_bgr.copy()
    result[grid_mask > 0] = [255, 255, 255]
    return result


def save_png(img_bgr: np.ndarray, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(dst), img_bgr)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Konwertuje PDF do PNG (jedna strona = jeden plik)."
    )
    parser.add_argument(
        "--input", required=True, type=Path,
        help="Plik PDF lub katalog z plikami PDF.",
    )
    parser.add_argument(
        "--output-dir", required=True, type=Path,
        help="Katalog wyjściowy. Dla każdego PDF tworzy podkatalog <stem>/.",
    )
    parser.add_argument(
        "--dpi", type=int, default=300,
        help="Rozdzielczość renderowania (domyślnie 300).",
    )
    parser.add_argument(
        "--rotate-180", action="store_true",
        help="Wymuś obrót wszystkich stron o 180°.",
    )
    parser.add_argument(
        "--auto-rotate", action="store_true",
        help="Auto-detekcja obrotu 180° na podstawie rozkładu atramentu.",
    )
    parser.add_argument(
        "--remove-grid", action="store_true",
        help="Usuń siatkę kratki z papieru (OpenCV morph).",
    )
    parser.add_argument(
        "--manifest", type=Path, default=None,
        help="Ścieżka do wyjściowego CSV z manifestem stron. "
             "Domyślnie <output-dir>/pages_manifest.csv.",
    )
    return parser


def process_pdf(
    pdf_path: Path,
    output_dir: Path,
    dpi: int,
    rotate_180: bool,
    auto_rotate: bool,
    remove_grid_flag: bool,
) -> list[dict]:
    pages = pdf_to_pixmaps(pdf_path, dpi)
    records: list[dict] = []
    subdir = output_dir / pdf_path.stem

    for page_num, img in pages:
        rotation_applied = "none"

        # 1. Wymuszony obrót
        if rotate_180:
            img = cv2.rotate(img, cv2.ROTATE_180)
            rotation_applied = "forced_180"

        # 2. Auto-detekcja (tylko jeśli nie wymuszono)
        elif auto_rotate:
            if detect_upside_down(img):
                img = cv2.rotate(img, cv2.ROTATE_180)
                rotation_applied = "auto_180"
            else:
                rotation_applied = "auto_ok"

        # 3. Usunięcie kratki
        if remove_grid_flag:
            img = remove_grid(img)

        dst = subdir / f"page_{page_num:03d}.png"
        save_png(img, dst)

        h, w = img.shape[:2]
        print(f"  strona {page_num:3d} → {dst.name}  ({w}×{h})  rot={rotation_applied}")
        records.append({
            "pdf":              str(pdf_path),
            "page_num":         page_num,
            "image_path":       str(dst),
            "width":            w,
            "height":           h,
            "rotation_applied": rotation_applied,
        })

    return records


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    args = build_parser().parse_args()

    input_path: Path = args.input.resolve()
    output_dir: Path = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = args.manifest or (output_dir / "pages_manifest.csv")

    # Zbierz pliki PDF
    if input_path.is_dir():
        pdfs = sorted(input_path.glob("*.pdf")) + sorted(input_path.glob("*.PDF"))
        if not pdfs:
            raise SystemExit(f"Brak plików PDF w {input_path}")
    elif input_path.suffix.lower() == ".pdf":
        pdfs = [input_path]
    else:
        raise SystemExit(f"Oczekiwano pliku PDF lub katalogu: {input_path}")

    all_records: list[dict] = []

    for pdf_path in pdfs:
        print(f"\nPrzetwarzam: {pdf_path.name}")
        records = process_pdf(
            pdf_path=pdf_path,
            output_dir=output_dir,
            dpi=args.dpi,
            rotate_180=args.rotate_180,
            auto_rotate=args.auto_rotate,
            remove_grid_flag=args.remove_grid,
        )
        all_records.extend(records)

    fieldnames = ["pdf", "page_num", "image_path", "width", "height", "rotation_applied"]
    with manifest_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_records)

    print(f"\nGotowe. {len(all_records)} stron → {output_dir}")
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
