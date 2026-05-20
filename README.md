# htr_gminy

Pipeline HTR (Handwritten Text Recognition) dla historycznych ksiąg metrykalnych i rejestrów administracyjnych gmin wiejskich.

**Dwa cele:**
1. **Trening** — historyczne księgi parafialne gminy Wysoka (XIX w.) jako zestaw treningowy
2. **Produkt docelowy** — rejestry wniosków o warunki zabudowy (WZ) z gmin wiejskich → Excel + QGIS

---

## ⚠️ Zasada: minimalizuj użycie płatnych API

**Gemini API generuje koszty. Używaj go tylko gdy nie ma alternatywy.**

| Zadanie | Właściwe podejście |
|---------|-------------------|
| OCR w produkcji (gotowy model) | **Kraken lokalnie** — zero kosztów |
| Generowanie GT dla nowego typu dokumentu | Gemini jednorazowo, potem review GUI + Kraken draft |
| Korekta wyników HTR | **Tylko jeśli CER > 10%** i ręczny review jest wolniejszy |
| Testowanie / debugowanie | Zawsze najpierw Kraken, Gemini tylko gdy Kraken kompletnie nie daje rady |

**Docelowy stan produkcyjny: Gemini w ogóle nie uczestniczy w przetwarzaniu.**  
Pipeline: `PDF → Kraken segmentacja → HTR (lokalny model) → parser → Excel → ULDK`

Gemini był potrzebny **jednorazowo** do bootstrapu datasetu treningowego.  
Gdy model osiągnie CER < 5% na dokumentach WZ — `gemini_ocr_pages.py` idzie na emeryturę.

---

## Środowisko

```
Python: C:\Users\...\AppData\Local\Programs\Python\Python312\python.exe
        (brak virtualenv — wszystko w systemowym Python 3.12)
ketos/kraken: w tym samym env
```

**Instalacja zależności na nowej maszynie:**
```powershell
pip install kraken ketos "google-genai" openpyxl
```

**Wymagana zmienna środowiskowa:**
```powershell
$env:GEMINI_API_KEY = "twój_klucz"   # potrzebny tylko do skryptów gemini_ocr_*.py
```

Klucz API Gemini: https://aistudio.google.com/app/apikey

**Naprawione bugi w bibliotece kraken (wymagane na każdej maszynie):**

`htrmopo/util.py` — dodać `encoding='utf-8'` do obu `open()` (iso15924.txt, iso639-3.txt):
```python
open(path, encoding='utf-8')
```

`kraken/lib/dataset/recognition.py:179` — dodać guard (bug: AttributeError gdy im_transforms=None + bbox + raw):
```python
# zmień: if self.transforms:
# na:
if self.transforms is not None:
```

---

## Modele

| Plik | Opis | Rozmiar |
|------|------|---------|
| `models/McCATMuS_nfd_nofix_V1.mlmodel` | Model bazowy McCATMuS — ogólny HTR XVI–XXI w. (wielojęzyczny) | 15 MB |
| `models/htr_docs_polish_v2.mlmodel` | Fine-tune na dokumentach Wysoka + POPP (epoch 16/30) | 15 MB |

**htr_wysoka_v2** — wyniki treningu:
- Dataset: 275 wierszy Wysoka (Gemini OCR) + 500 wierszy POPP (franc. rejestry cywilne 1920s)
- Najlepszy checkpoint: epoch 16, **~87.97% accuracy (CER ~12%)**
- Po epoch 16 overfitting → accuracy spada do ~84.9%
- Model roboczy, nie produkcyjny. Docelowy CER: <5–7%

> **Uwaga:** Wszystkie dokumenty w tym projekcie to **ręczne pismo**. Nigdy nie zakładaj druku.

---

## Struktura katalogów

```
htr_gminy/
├── models/
│   ├── McCATMuS_nfd_nofix_V1.mlmodel   # model bazowy
│   └── htr_docs_polish_v2.mlmodel           # aktualny model roboczy
├── scripts/                             # wszystkie skrypty (opis niżej)
├── outputs/                             # ← w .gitignore, nie ma w repo
│   └── training/
│       ├── training_manifest.csv        # GŁÓWNY PLIK DATASETU (299 wierszy)
│       └── ground-truth/<strona>/*.png  # wycięte wiersze + *.gt.txt
└── external_data/                       # ← w .gitignore, nie ma w repo
    └── popp/                            # dataset POPP (Zenodo 6581158)
```

Skany źródłowe Wysoka: wzorzec `92_54_0_15_384_N_*.jpg` — nie ma ich w repo.

---

## Główny pipeline (trening)

### Krok 1 — OCR stron przez Gemini

```powershell
$env:GEMINI_API_KEY = "klucz"
python scripts\gemini_ocr_pages.py `
    --input-dir  <folder_ze_skanami> `
    --output-csv outputs\ocr_pages.csv
```

Wyjście: `ocr_pages.csv` (kolumny: `source`, `row`, `cols_json`)  
Model: `gemini-2.5-flash`, opóźnienie 6s między requestami (rate limit free tier).

### Krok 2 — Segmentacja + budowanie datasetu

```powershell
python scripts\build_training_from_blla.py `
    --input-dir  <folder_ze_skanami> `
    --ocr-csv    outputs\ocr_pages.csv `
    --output-dir outputs\training `
    --skip-first-rows 1
```

Co robi:
- Kraken segmentuje każdą stronę (`blla` — baseline layout analysis)
- Grupuje linie po Y-współrzędnej w klastry wierszy tabeli
- Matchuje klaster N z wierszem OCR N (offset = `--skip-first-rows`)
- Wycina PNG każdego wiersza → `ground-truth/<strona>/<idx>.png`
- Tworzy `training_manifest.csv`

**⚠️ Główna pułapka: wyrównanie wierszy**

Skrypt zakłada `klaster[N] == OCR[N]`. Psuje się gdy:
- Strona ma dodatkowy nagłówek kolumn (wtedy `--skip-first-rows 2`)
- Gemini numeruje OCR ciągle przez strony (np. strona 13: wiersze 35–69 zamiast 1–35)

Auto-detekcja offsetu w `fix_and_clean.py` jest zawodna dla stron z ciągłą numeracją — **nie ufać jej bez ręcznej weryfikacji.**

Strony z historycznie problematycznym wyrównaniem: 13 (offset=+35), 16, 17, 18, 20, 24 (extra klaster na końcu), 21, 23 (niezgodności ±2–6), 15, 22, 26, 28 (cluster_count < ocr_count), 27 (brak OCR).

### Krok 3 — Review GUI

```powershell
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
python scripts\review_gui_server.py `
    --manifest outputs\training\training_manifest.csv `
    --port 8766
# otwórz http://127.0.0.1:8766
```

Skróty klawiszowe:
- `Ctrl+S` — zapisz
- `←` / `→` — poprzedni / następny rekord
- `Ctrl+Scroll` — zoom obrazka

Funkcje:
- Przyciski "OCR strona −1/+1" (fioletowe) — przesuwa OCR dla całej strony o ±1 wiersz (naprawa offsetu)
- Status: `todo` → `ready` (zatwierdzone)
- Usuń wiersz: czerwony przycisk (usuwa z manifestu, pliki PNG zostają na dysku)

### Krok 4 — Fine-tuning

```powershell
python scripts\run_ketos_finetune.py `
    --ground-truth-dir outputs\training\ground-truth `
    --output-dir       outputs\model_v3 `
    --base-model       models\htr_docs_polish_v2.mlmodel `
    --manifest         outputs\training\training_manifest.csv `
    --only-ready `
    --epochs           30 `
    --batch-size       4 `
    --learning-rate    0.0005 `
    --device           cpu
```

Opcjonalnie z POPP (lepsza generalizacja):
```powershell
    --extra-gt-dirs     external_data\popp\ground-truth `
    --max-extra-samples 500
```

Ketos tworzy checkpointy `outputs\model_v3\*.mlmodel` — najlepszy to plik z najwyższym score w nazwie.

Wybierz najlepszy checkpoint:
```powershell
python scripts\finalize_model.py --model-dir outputs\model_v3 --output models\htr_wysoka_v3.mlmodel
```

> **Uwaga Windows — WinError 206** (zbyt długa linia komend przy dużym datasecie):  
> `run_ketos_finetune.py` używa Python API (`build_binary_dataset`) zamiast subprocess. Nie zamieniaj na subprocess z listą plików.

---

## Szybki test modelu

```powershell
kraken -i <skan.jpg> wynik.txt ocr -m models\htr_docs_polish_v2.mlmodel
```

---

## Stan datasetu Wysoka (2026-05-07)

| Status | Liczba |
|--------|--------|
| `ready` (zrecenzowane, użyte w v2) | 68 |
| bez statusu (do review) | 228 |
| `todo` | 1 |
| **ŁĄCZNIE** | **299** |

Do osiągnięcia CER <7% potrzeba ~300–500 wierszy `ready`.  
**Następny krok:** zreviewować pozostałe 228 wierszy → retraining v3.

---

## Dataset POPP (opcjonalny)

Zenodo 6581158 — ~6030 linii z francuskich rejestrów cywilnych lat 20. XX w.  
Używany jako augmentacja (różnorodne pismo odręczne → lepsza generalizacja).

```powershell
# Pobierz: https://zenodo.org/record/6581158 → popp.zip
# Rozpakuj do external_data/popp/
python scripts\convert_popp.py `
    --input-dir  external_data\popp `
    --output-dir external_data\popp\ground-truth
```

---

## Produkt docelowy — pipeline WZ

**Kontekst:** pracodawca chce wychwytywać adresy działek z wniosków WZ, sprawdzać podziały działek i mapować w QGIS.

**Dokumenty:** ręcznie wypełnione rejestry WZ z gmin wiejskich — PDF, często na papierze w kratkę, często obrócone o 180°.

**Format adresu:** `Sanniki 45,46` (nazwa miejscowości + numery działek — brak ulic, format wiejski).

**7 kolumn tabeli (bez nagłówków):**
```
Lp | Nr(?) | Opis inwestycji | Miejscowość + nr działki | Wnioskodawca | Werdykt | ?(do ustalenia)
```

Werdykt: słowny (pozytywny / negatywny / odmowa) + numer decyzji.

### Pipeline docelowy

```
PDF
 └─► pymupdf → strony PNG (300 dpi)
       └─► wykryj orientację → obróć jeśli 180°
             └─► deskew
                   └─► usuń kratkę (OpenCV morph)
                         └─► adaptive threshold
                               └─► Kraken segmentacja (blla)
                                     └─► HTR (nasz model)
                                           └─► Gemini korekta
                                                 └─► parser 7 kolumn (po X bbox)
                                                       ├─► regex: miejscowość + nr działek
                                                       ├─► regex: werdykt + nr decyzji
                                                       └─► DataFrame
                                                             ├─► Excel (.xlsx)
                                                             ├─► ULDK API → weryfikacja działek
                                                             └─► GeoPackage/CSV → QGIS
```

### Krok 0 — PDF → PNG (pierwsza rzecz do zrobienia)

```powershell
# Normalnie:
python scripts\pdf_to_pages.py --input rejestr.pdf --output-dir outputs\pages\

# Strony obrócone o 180° (częsty przypadek w skanach WZ):
python scripts\pdf_to_pages.py --input rejestr.pdf --output-dir outputs\pages\ --rotate-180

# Nie wiesz czy obrócone — auto-detekcja:
python scripts\pdf_to_pages.py --input rejestr.pdf --output-dir outputs\pages\ --auto-rotate

# Papier w kratkę (usuwa siatkę przed HTR):
python scripts\pdf_to_pages.py --input rejestr.pdf --output-dir outputs\pages\ --auto-rotate --remove-grid

# Cały katalog PDFów naraz:
python scripts\pdf_to_pages.py --input katalog_z_pdf/ --output-dir outputs\pages\ --auto-rotate --remove-grid
```

Wyjście: `outputs/pages/<nazwa_pdf>/page_001.png`, `page_002.png`, ... + `pages_manifest.csv`

Następny krok po konwersji: `gemini_ocr_pages.py` na folderze z PNG lub `build_training_from_blla.py`.

**Strategia HTR + Gemini:**  
Kraken daje draft ~88% accuracy, Gemini poprawia resztę używając kontekstu (polskie nazwiska, daty, numery decyzji). Taniej niż dawać Gemini surowy obraz za każdym razem.

### Krok 2 — parsowanie 7 kolumn → Excel

```powershell
python scripts\parse_wz_output.py `
    --input  outputs\ocr_pages.csv `
    --output outputs\rejestry_wz.xlsx `
    --teryt  1430022

# Jeśli kolumny w Twoich dokumentach są w innej kolejności:
python scripts\parse_wz_output.py `
    --input  outputs\ocr_pages.csv `
    --output outputs\rejestry_wz.xlsx `
    --teryt  1430022 `
    --col-dzialka 3 --col-werdykt 5 --col-nr-decyzji 6
```

Wyjście: `rejestry_wz.xlsx` (kolorowany werdykt) + `rejestry_wz_do_weryfikacji.csv` (dla ULDK).

### Krok 3 — weryfikacja działek ULDK

```powershell
# Znasz numer obrębu:
python scripts\uldk_verify.py `
    --input  outputs\rejestry_wz_do_weryfikacji.csv `
    --output outputs\rejestry_wz_zweryfikowane.xlsx `
    --teryt  1430022 `
    --obreb  0001

# Nie znasz obrębu (szuka po numerze działki w całej gminie):
python scripts\uldk_verify.py `
    --input  outputs\rejestry_wz_do_weryfikacji.csv `
    --output outputs\rejestry_wz_zweryfikowane.xlsx `
    --teryt  1430022

# Sprawdź też podpodziały (45 → 45/1, 45/2 itd.):
python scripts\uldk_verify.py `
    --input  outputs\rejestry_wz_do_weryfikacji.csv `
    --output outputs\rejestry_wz_zweryfikowane.xlsx `
    --teryt  1430022 --obreb 0001 --check-subdivisions
```

Kody TERYT gmin: https://teryt.stat.gov.pl/

**ULDK API** (weryfikacja działek):
```
https://uldk.gugik.gov.pl/?request=GetParcelById&id={TERYT}.{obreb}.{nr}
```
- Obręb = nazwa miejscowości
- Numer działki może mieć podpodziały: `45`, `45/1`, `45/2` itp.
- TERYT gminy: parametr wejściowy (różny dla każdej gminy)
- Układ współrzędnych: EPSG:2180

> **RODO:** Skany WZ zawierają nazwiska wnioskodawców. **Nigdy nie wrzucać do repo ani na zewnętrzne serwisy bez zgody.** Sam model i skrypty są czyste — zero danych osobowych.

---

## Skrypty — opis

| Skrypt | Opis |
|--------|------|
| `gemini_ocr_pages.py` | OCR całych stron przez Gemini → CSV (`source`, `row`, `cols_json`) |
| `gemini_ocr_cells.py` | OCR pojedynczych komórek przez Gemini |
| `build_training_from_blla.py` | Segmentacja Kraken blla + match z OCR → dataset PNG + manifest |
| `review_gui_server.py` | Serwer GUI do review datasetu (port 8766) |
| `run_ketos_finetune.py` | Kompiluje dataset.arrow + uruchamia trening ketos |
| `finalize_model.py` | Wybiera najlepszy checkpoint z katalogu → zapisuje jako .mlmodel |
| `convert_popp.py` | Konwertuje dataset POPP do formatu PNG + gt.txt |
| `analyze_alignment.py` | Diagnostyka per-page offsetów: ile klastrów vs ile wierszy OCR |
| `fix_and_clean.py` | Auto-naprawa offsetów (**zawodna** dla ciągłej numeracji, sprawdzać ręcznie) |
| `fix_page13_offset.py` | Jednorazowy fix strony 13 (prawidłowy offset=+35) |
| `fix_page10_alignment.py` | Jednorazowy fix strony 10 (skip=2) |
| `preprocess_handwritten.py` | Preprocessing obrazów (deskew, threshold, usuwanie kratki) |
| `split_table_columns.py` | Podział tabeli na kolumny po X bbox |
| `split_column_cells.py` | Wycięcie komórek z pojedynczej kolumny |
| `run_kraken_page_ocr.py` | Kraken OCR na całej stronie (segmentacja + rozpoznanie) |
| `run_kraken_line_ocr.py` | Kraken OCR na gotowych wierszach |
| `check_seg.py`, `check_seg2.py` | Wizualizacja wyników segmentacji |
| `build_review_html.py` | Buduje statyczny HTML z podglądem review |
| `match_ocr_to_cells.py` | Łączy wyniki Gemini OCR z wyciętymi komórkami tabeli |
| `make_source_manifest.py` | Tworzy manifest źródłowy dla nowego zestawu skanów |
| `pdf_to_pages.py` | PDF → PNG (300 dpi), auto-rotate 180°, usuwanie kratki |
| `parse_wz_output.py` | Gemini CSV (cols_json) → parsuje 7 kolumn → Excel (.xlsx) |
| `uldk_verify.py` | Weryfikacja numerów działek przez ULDK API gugik.gov.pl |
| `test_gemini_ocr.py` | Szybki test OCR Gemini na jednym obrazku |

---

## Git workflow na nowej maszynie

```powershell
git clone https://github.com/Rektos721/htr_gminy
cd htr_gminy

# Modele są w repo (models/*.mlmodel) — gotowe do użycia.
# Skany i dane treningowe musisz mieć lokalnie — nie ma ich w repo.

# Ustaw klucz Gemini jeśli używasz OCR:
$env:GEMINI_API_KEY = "klucz"
```

Po wytrenowaniu nowego modelu:
```powershell
git add models\htr_wz_v1.mlmodel
git commit -m "add model htr_wz_v1 (epoch X, acc Y%)"
git push
```
