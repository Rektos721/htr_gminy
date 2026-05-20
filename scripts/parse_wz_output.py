"""parse_wz_output.py — parsuje wynik Gemini OCR (cols_json CSV) do strukturalnego Excel.

Wejście:  ocr_pages.csv z gemini_ocr_pages.py (kolumny: source, row, cols_json)
Wyjście:  rejestry_wz.xlsx + rejestry_wz.csv

Kolumny wejściowe (konfigurowalne przez --col-*):
  Domyślny układ (indeksy 0-based):
    0 = Lp
    1 = Data / Nr wniosku
    2 = Wnioskodawca
    3 = Adres inwestycji
    4 = Numer działki  (np. "dz. nr 45/1 obr. Sanniki")
    5 = Numer decyzji  (np. "WZ/2024/001")
    6 = Werdykt        (np. "pozytywna")

  Jeśli układ w Twoich dokumentach jest inny, podaj --col-dzialka 3 --col-werdykt 5 itp.
  Jeśli numer decyzji jest w tej samej komórce co werdykt, skrypt spróbuje go wyciągnąć regexem.

Użycie:
    python scripts/parse_wz_output.py \\
        --input  outputs/ocr_pages.csv \\
        --output outputs/rejestry_wz.xlsx \\
        --teryt  0214052
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

try:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False


# ---------------------------------------------------------------------------
# Regex
# ---------------------------------------------------------------------------

# Numery działek: 45  45/1  45/1,45/2  dz. nr 45/1 obr. ...
RE_DZIALKA_NR = re.compile(r'\b(\d+(?:/\d+)?)\b')

# Nazwa miejscowości + numery działek z pola tekstowego
# Przykłady: "Sanniki 45,46"  "Brudzeń Duży dz. nr 45/1, 46"
RE_MIEJSCOWOSC_DZIALKI = re.compile(
    r'^([A-ZŁŚŹŻĄĘĆÓŃ][a-zA-ZłśźżąęćóńŁŚŹŻĄĘĆÓŃ\s\-]+?)\s+'  # nazwa miejscowości
    r'(?:dz\.?\s*(?:nr\.?)?\s*)?'                                # opcjonalne "dz. nr"
    r'([\d,;/\s]+)',                                              # numery działek
    re.IGNORECASE,
)

# Numer decyzji: WZ/2024/001  WZ.2024.1  123/WZ/2024  RIiGN.6730.1.2024
RE_NR_DECYZJI = re.compile(
    r'\b([A-Z]{1,10}[.\-/]\d{1,5}[.\-/]\d{1,5}(?:[.\-/]\d{1,5})?)\b'
)

# Werdykt
WERDYKT_MAPA = {
    'pozytyw':  'POZYTYWNA',
    'wydano':   'POZYTYWNA',
    'ustalono': 'POZYTYWNA',
    'negatyw':  'NEGATYWNA',
    'odmow':    'ODMOWA',
    'odmówi':   'ODMOWA',
    'umorzon':  'UMORZENIE',
    'wycofan':  'WYCOFANIE',
}


def parse_werdykt(tekst: str) -> str:
    t = tekst.lower()
    for fragment, wynik in WERDYKT_MAPA.items():
        if fragment in t:
            return wynik
    return 'NIEZNANY' if tekst.strip() else ''


def parse_nr_decyzji(tekst: str) -> str:
    m = RE_NR_DECYZJI.search(tekst)
    return m.group(1) if m else ''


def parse_dzialki(tekst: str) -> tuple[str, list[str]]:
    """Zwraca (miejscowość, [numery_działek])."""
    m = RE_MIEJSCOWOSC_DZIALKI.match(tekst.strip())
    if m:
        miejscowosc = m.group(1).strip()
        nr_raw = m.group(2)
        numery = [x.strip() for x in re.split(r'[,;\s]+', nr_raw) if RE_DZIALKA_NR.match(x.strip())]
        return miejscowosc, numery
    # Fallback: wyciągnij same numery bez rozpoznania miejscowości
    numery = RE_DZIALKA_NR.findall(tekst)
    return '', numery


# ---------------------------------------------------------------------------
# Excel output
# ---------------------------------------------------------------------------

HEADER_FILL   = PatternFill('solid', fgColor='1F3864') if HAS_OPENPYXL else None
HEADER_FONT   = Font(bold=True, color='FFFFFF') if HAS_OPENPYXL else None
ALT_FILL      = PatternFill('solid', fgColor='DCE6F1') if HAS_OPENPYXL else None

VERDICT_COLORS = {
    'POZYTYWNA':  'C6EFCE',
    'NEGATYWNA':  'FFC7CE',
    'ODMOWA':     'FFC7CE',
    'UMORZENIE':  'FFEB9C',
    'WYCOFANIE':  'FFEB9C',
}

OUTPUT_COLS = [
    'source', 'row',
    'lp', 'data_wniosku', 'wnioskodawca',
    'adres_inwestycji', 'miejscowosc', 'numery_dzialek',
    'nr_decyzji', 'werdykt', 'werdykt_raw',
    'col_raw_full',
]


def write_excel(rows: list[dict], path: Path) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Rejestr WZ'

    # Nagłówek
    for ci, col in enumerate(OUTPUT_COLS, start=1):
        cell = ws.cell(row=1, column=ci, value=col.upper().replace('_', ' '))
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal='center', wrap_text=True)

    ws.row_dimensions[1].height = 30

    for ri, row in enumerate(rows, start=2):
        fill = ALT_FILL if ri % 2 == 0 else None
        werdykt = row.get('werdykt', '')
        verdict_fill_color = VERDICT_COLORS.get(werdykt)
        verdict_fill = PatternFill('solid', fgColor=verdict_fill_color) if verdict_fill_color else fill

        for ci, col in enumerate(OUTPUT_COLS, start=1):
            val = row.get(col, '')
            cell = ws.cell(row=ri, column=ci, value=val)
            if col == 'werdykt' and verdict_fill:
                cell.fill = verdict_fill
            elif fill:
                cell.fill = fill
            cell.alignment = Alignment(wrap_text=True, vertical='top')

    # Szerokości kolumn
    col_widths = {
        'SOURCE': 20, 'ROW': 5, 'LP': 5,
        'DATA WNIOSKU': 14, 'WNIOSKODAWCA': 25,
        'ADRES INWESTYCJI': 30, 'MIEJSCOWOSC': 18, 'NUMERY DZIALEK': 20,
        'NR DECYZJI': 18, 'WERDYKT': 14, 'WERDYKT RAW': 20,
        'COL RAW FULL': 50,
    }
    for ci, col in enumerate(OUTPUT_COLS, start=1):
        key = col.upper().replace('_', ' ')
        ws.column_dimensions[get_column_letter(ci)].width = col_widths.get(key, 15)

    ws.freeze_panes = 'A2'
    wb.save(str(path))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Parsuje wynik Gemini OCR (cols_json) → strukturalny Excel/CSV."
    )
    p.add_argument('--input',   required=True, type=Path,
                   help='ocr_pages.csv z gemini_ocr_pages.py')
    p.add_argument('--output',  required=True, type=Path,
                   help='Wyjściowy plik .xlsx (lub .csv jeśli brak openpyxl)')
    p.add_argument('--teryt',   default='', type=str,
                   help='Kod TERYT gminy (7 cyfr) — zapisywany w manifeście dla uldk_verify.py')

    # Mapowanie kolumn (0-based)
    p.add_argument('--col-lp',          type=int, default=0)
    p.add_argument('--col-data',        type=int, default=1)
    p.add_argument('--col-wnioskodawca',type=int, default=2)
    p.add_argument('--col-adres',       type=int, default=3)
    p.add_argument('--col-dzialka',     type=int, default=4,
                   help='Kolumna z numerem działki i/lub miejscowością')
    p.add_argument('--col-nr-decyzji',  type=int, default=5)
    p.add_argument('--col-werdykt',     type=int, default=6)
    return p


def get_col(cols: list[str], idx: int) -> str:
    return cols[idx].strip() if idx < len(cols) else ''


def main() -> None:
    sys.stdout.reconfigure(encoding='utf-8')
    args = build_parser().parse_args()

    if not args.input.exists():
        raise SystemExit(f'Brak pliku: {args.input}')

    if not HAS_OPENPYXL and args.output.suffix == '.xlsx':
        print('Uwaga: brak openpyxl — zapis do CSV zamiast Excel. pip install openpyxl')

    with args.input.open(encoding='utf-8', newline='') as f:
        reader = csv.DictReader(f)
        source_rows = list(reader)

    if not source_rows:
        raise SystemExit('Plik CSV jest pusty.')

    out_rows: list[dict] = []

    for src in source_rows:
        raw_cols_json = src.get('cols_json', '[]')
        try:
            cols = json.loads(raw_cols_json)
        except json.JSONDecodeError:
            cols = []

        if not cols:
            continue

        # Surowe wartości z kolumn
        lp             = get_col(cols, args.col_lp)
        data_wniosku   = get_col(cols, args.col_data)
        wnioskodawca   = get_col(cols, args.col_wnioskodawca)
        adres          = get_col(cols, args.col_adres)
        dzialka_raw    = get_col(cols, args.col_dzialka)
        nr_dec_raw     = get_col(cols, args.col_nr_decyzji)
        werdykt_raw    = get_col(cols, args.col_werdykt)

        # Parsowanie działki
        miejscowosc, numery = parse_dzialki(dzialka_raw)

        # Numer decyzji — najpierw z dedykowanej kolumny, potem szukaj w werdykcie
        nr_decyzji = parse_nr_decyzji(nr_dec_raw) or parse_nr_decyzji(werdykt_raw)

        # Werdykt
        werdykt = parse_werdykt(werdykt_raw)

        out_rows.append({
            'source':          src.get('source', ''),
            'row':             src.get('row', ''),
            'lp':              lp,
            'data_wniosku':    data_wniosku,
            'wnioskodawca':    wnioskodawca,
            'adres_inwestycji': adres,
            'miejscowosc':     miejscowosc,
            'numery_dzialek':  ', '.join(numery),
            'nr_decyzji':      nr_decyzji,
            'werdykt':         werdykt,
            'werdykt_raw':     werdykt_raw,
            'col_raw_full':    raw_cols_json,
            '_teryt':          args.teryt,         # dla uldk_verify.py
        })

        print(f"  r{src.get('row'):>3}: {lp:>3} | {wnioskodawca[:20]:<20} | "
              f"{miejscowosc:<15} {', '.join(numery):<12} | {werdykt}")

    print(f'\nSparsowano {len(out_rows)} wierszy.')

    # Zapis Excel
    args.output.parent.mkdir(parents=True, exist_ok=True)

    if HAS_OPENPYXL and args.output.suffix == '.xlsx':
        write_excel(out_rows, args.output)
        print(f'Excel: {args.output}')
    else:
        csv_path = args.output.with_suffix('.csv')
        with csv_path.open('w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=OUTPUT_COLS)
            writer.writeheader()
            writer.writerows({k: v for k, v in r.items() if k in OUTPUT_COLS} for r in out_rows)
        print(f'CSV: {csv_path}')

    # Zawsze zapisz też CSV dla uldk_verify.py
    verify_csv = args.output.with_name(args.output.stem + '_do_weryfikacji.csv')
    verify_cols = ['source', 'row', 'lp', 'wnioskodawca', 'miejscowosc',
                   'numery_dzialek', 'nr_decyzji', 'werdykt', '_teryt']
    with verify_csv.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=verify_cols)
        writer.writeheader()
        for r in out_rows:
            writer.writerow({k: r.get(k, '') for k in verify_cols})
    print(f'Do weryfikacji ULDK: {verify_csv}')


if __name__ == '__main__':
    main()
