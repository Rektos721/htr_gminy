"""uldk_verify.py — weryfikuje numery działek przez API ULDK (gugik.gov.pl).

Wejście:  CSV z parse_wz_output.py (*_do_weryfikacji.csv)
Wyjście:  CSV + Excel z wynikami weryfikacji

API ULDK: https://uldk.gugik.gov.pl/
  GetParcelById      — dokładne wyszukiwanie po pełnym ID (TERYT.OBREB.NR)
  GetParcelByParcelId — wyszukiwanie po numerze działki w obrębie gminy

ID format: {TERYT_7}.{OBREB_4}.{NR_DZIALKI}
  Przykład: 1430022.0001.45/1

Jeśli nie znasz numeru obrębu — podaj --obreb "" a skrypt spróbuje
GetParcelByParcelId z samym TERYT i numerem działki.

Historia podziałów: skrypt szuka automatycznie 45/1, 45/2, ... gdy
działka 45 nie istnieje lub gdy --check-subdivisions.

Użycie:
    python scripts/uldk_verify.py \\
        --input  outputs/rejestry_wz_do_weryfikacji.csv \\
        --output outputs/rejestry_wz_zweryfikowane.xlsx \\
        --teryt  1430022 \\
        --obreb  0001

    # Bez znajomości obrębu (wolniejsze, szuka po numerze):
    python scripts/uldk_verify.py \\
        --input  outputs/rejestry_wz_do_weryfikacji.csv \\
        --output outputs/rejestry_wz_zweryfikowane.xlsx \\
        --teryt  1430022
"""
from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path
from urllib.request import urlopen
from urllib.parse import urlencode
from urllib.error import URLError

try:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False


ULDK_BASE = 'https://uldk.gugik.gov.pl/'
ULDK_RESULT_FIELDS = 'teryt,pow_m2,voivodeship,county,commune,region,parcel'
DELAY = 0.5  # sekund między requestami


# ---------------------------------------------------------------------------
# ULDK API
# ---------------------------------------------------------------------------

def uldk_get(params: dict) -> str:
    """Wykonuje request do ULDK, zwraca surową odpowiedź tekstową."""
    url = ULDK_BASE + '?' + urlencode(params)
    try:
        with urlopen(url, timeout=10) as resp:
            return resp.read().decode('utf-8').strip()
    except URLError as e:
        return f'ERROR:{e}'


def parse_uldk_response(text: str) -> dict:
    """Parsuje odpowiedź ULDK.

    Sukces: pierwsza linia to '0', kolejne linie to wyniki.
    Brak:   pierwsza linia to '-1' lub pusta.
    Błąd:   zaczyna się od 'ERROR:'.
    """
    if text.startswith('ERROR:'):
        return {'status': 'error', 'raw': text}
    lines = [l for l in text.splitlines() if l.strip()]
    if not lines:
        return {'status': 'not_found', 'raw': text}
    if lines[0] == '-1' or lines[0].startswith('-1'):
        return {'status': 'not_found', 'raw': text}
    if lines[0] == '0':
        results = lines[1:]
        return {'status': 'found', 'count': len(results), 'results': results, 'raw': text}
    # Niektóre endpointy od razu zwracają dane (bez kodu statusu)
    return {'status': 'found', 'count': len(lines), 'results': lines, 'raw': text}


def lookup_parcel(teryt: str, obreb: str, nr: str) -> dict:
    """Szuka działki. Jeśli obreb pusty — używa GetParcelByParcelId."""
    if obreb:
        parcel_id = f'{teryt}.{obreb}.{nr}'
        resp = uldk_get({'request': 'GetParcelById', 'id': parcel_id,
                         'result': ULDK_RESULT_FIELDS})
    else:
        # Bez obrębu — szukamy po numerze w gminie
        parcel_id = f'{teryt}.{nr}'
        resp = uldk_get({'request': 'GetParcelByParcelId', 'id': parcel_id,
                         'result': ULDK_RESULT_FIELDS})
    result = parse_uldk_response(resp)
    result['queried_id'] = parcel_id
    return result


def find_subdivisions(teryt: str, obreb: str, nr_base: str, max_sub: int = 10) -> list[str]:
    """Szuka podziałów: 45/1, 45/2, ... aż do max_sub nieznalezionych z rzędu."""
    found: list[str] = []
    miss = 0
    i = 1
    while miss < 3 and i <= max_sub:
        sub_nr = f'{nr_base}/{i}'
        result = lookup_parcel(teryt, obreb, sub_nr)
        time.sleep(DELAY)
        if result['status'] == 'found':
            found.append(sub_nr)
            miss = 0
        else:
            miss += 1
        i += 1
    return found


# ---------------------------------------------------------------------------
# Przetwarzanie wierszy
# ---------------------------------------------------------------------------

def verify_row(row: dict, teryt: str, obreb: str, check_subs: bool) -> dict:
    numery_raw = row.get('numery_dzialek', '').strip()
    miejscowosc = row.get('miejscowosc', '').strip()

    if not numery_raw:
        return {**row,
                'uldk_status': 'brak_numeru',
                'uldk_znalezione': '',
                'uldk_podzielone_na': '',
                'uldk_pow_m2': '',
                'uldk_teryt_full': ''}

    numery = [n.strip() for n in numery_raw.split(',') if n.strip()]

    znalezione: list[str] = []
    podzielone: list[str] = []
    pow_m2_list: list[str] = []
    teryt_full_list: list[str] = []

    for nr in numery:
        result = lookup_parcel(teryt, obreb, nr)
        time.sleep(DELAY)

        if result['status'] == 'found':
            znalezione.append(nr)
            # Wyciągnij pow_m2 i teryt z pierwszego wyniku
            if result.get('results'):
                parts = result['results'][0].split(';')
                if len(parts) >= 2:
                    teryt_full_list.append(parts[0])
                    pow_m2_list.append(parts[1])
        else:
            # Nie znaleziono — może podzielona?
            if check_subs:
                subs = find_subdivisions(teryt, obreb, nr)
                if subs:
                    podzielone.append(f'{nr}→[{", ".join(subs)}]')
                    znalezione.extend(subs)

    status = 'ok' if znalezione else 'nie_znaleziono'
    if podzielone:
        status = 'podzielone'

    return {
        **row,
        'uldk_status':        status,
        'uldk_znalezione':    ', '.join(znalezione),
        'uldk_podzielone_na': ', '.join(podzielone),
        'uldk_pow_m2':        ', '.join(pow_m2_list),
        'uldk_teryt_full':    ', '.join(teryt_full_list),
    }


# ---------------------------------------------------------------------------
# Excel output
# ---------------------------------------------------------------------------

STATUS_COLORS = {
    'ok':            'C6EFCE',
    'podzielone':    'FFEB9C',
    'nie_znaleziono':'FFC7CE',
    'brak_numeru':   'D9D9D9',
    'error':         'FF0000',
}

OUT_COLS = [
    'source', 'row', 'lp', 'wnioskodawca', 'miejscowosc', 'numery_dzialek',
    'nr_decyzji', 'werdykt',
    'uldk_status', 'uldk_znalezione', 'uldk_podzielone_na', 'uldk_pow_m2', 'uldk_teryt_full',
]


def write_excel(rows: list[dict], path: Path) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Weryfikacja działek'

    header_fill = PatternFill('solid', fgColor='1F3864')
    header_font = Font(bold=True, color='FFFFFF')

    for ci, col in enumerate(OUT_COLS, start=1):
        cell = ws.cell(row=1, column=ci, value=col.upper().replace('_', ' '))
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center', wrap_text=True)
    ws.row_dimensions[1].height = 28

    for ri, row in enumerate(rows, start=2):
        status = row.get('uldk_status', '')
        row_fill_color = STATUS_COLORS.get(status)
        for ci, col in enumerate(OUT_COLS, start=1):
            cell = ws.cell(row=ri, column=ci, value=row.get(col, ''))
            if row_fill_color and col == 'uldk_status':
                cell.fill = PatternFill('solid', fgColor=row_fill_color)
            cell.alignment = Alignment(wrap_text=True, vertical='top')

    col_widths = [20, 5, 5, 25, 18, 20, 18, 14, 16, 22, 25, 12, 22]
    for ci, w in enumerate(col_widths, start=1):
        ws.column_dimensions[get_column_letter(ci)].width = w

    ws.freeze_panes = 'A2'
    wb.save(str(path))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description='Weryfikuje numery działek WZ przez API ULDK gugik.gov.pl.'
    )
    p.add_argument('--input',   required=True, type=Path,
                   help='CSV z parse_wz_output.py (*_do_weryfikacji.csv)')
    p.add_argument('--output',  required=True, type=Path,
                   help='Wyjściowy .xlsx lub .csv z wynikami weryfikacji')
    p.add_argument('--teryt',   default='', type=str,
                   help='Kod TERYT gminy (7 cyfr, np. 1430022). '
                        'Jeśli pusty — bierze z kolumny _teryt w CSV.')
    p.add_argument('--obreb',   default='', type=str,
                   help='Numer obrębu (4 cyfry, np. 0001). '
                        'Jeśli pusty — szuka po samym numerze działki (wolniejsze).')
    p.add_argument('--check-subdivisions', action='store_true',
                   help='Dla nieznalezionych działek sprawdź podpodziały (45/1, 45/2 itd.)')
    p.add_argument('--delay',   type=float, default=DELAY,
                   help=f'Opóźnienie między requestami ULDK w sekundach (domyślnie {DELAY})')
    return p


def main() -> None:
    global DELAY
    sys.stdout.reconfigure(encoding='utf-8')
    args = build_parser().parse_args()
    DELAY = args.delay

    if not args.input.exists():
        raise SystemExit(f'Brak pliku: {args.input}')

    with args.input.open(encoding='utf-8', newline='') as f:
        rows = list(csv.DictReader(f))

    if not rows:
        raise SystemExit('Plik CSV jest pusty.')

    print(f'Wierszy do weryfikacji: {len(rows)}')
    print(f'TERYT: {args.teryt or "(z kolumny _teryt)"}  Obręb: {args.obreb or "(auto)"}')
    print()

    out_rows: list[dict] = []
    for i, row in enumerate(rows, start=1):
        teryt = args.teryt or row.get('_teryt', '')
        if not teryt:
            print(f'  [{i:3d}] POMINIĘTO — brak TERYT (podaj --teryt lub ustaw w CSV)')
            out_rows.append({**row, 'uldk_status': 'brak_teryt',
                             'uldk_znalezione': '', 'uldk_podzielone_na': '',
                             'uldk_pow_m2': '', 'uldk_teryt_full': ''})
            continue

        result_row = verify_row(row, teryt, args.obreb, args.check_subdivisions)
        status = result_row['uldk_status']
        nr = row.get('numery_dzialek', '')
        miejsc = row.get('miejscowosc', '')
        print(f'  [{i:3d}] {miejsc:<15} {nr:<15} → {status}  {result_row.get("uldk_znalezione","")}')
        out_rows.append(result_row)

    # Statystyki
    statuses = [r.get('uldk_status', '') for r in out_rows]
    print(f'\nPodsumowanie:')
    for s in ['ok', 'podzielone', 'nie_znaleziono', 'brak_numeru', 'brak_teryt', 'error']:
        n = statuses.count(s)
        if n:
            print(f'  {s:<20} {n}')

    # Zapis
    args.output.parent.mkdir(parents=True, exist_ok=True)

    if HAS_OPENPYXL and args.output.suffix == '.xlsx':
        write_excel(out_rows, args.output)
        print(f'\nExcel: {args.output}')
    else:
        csv_path = args.output.with_suffix('.csv')
        with csv_path.open('w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=OUT_COLS)
            writer.writeheader()
            writer.writerows({k: r.get(k, '') for k in OUT_COLS} for r in out_rows)
        print(f'\nCSV: {csv_path}')


if __name__ == '__main__':
    main()
