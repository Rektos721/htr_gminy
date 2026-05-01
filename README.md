# Handwritten HTR Workspace

Minimalny warsztat do testow `handwritten -> layout -> review -> training`.

## Co trzymac w repo

- `scripts/`
- `README.md`
- `.gitignore`

Nie wrzucaj do repo:

- `outputs/`
- `models/`
- prywatnych skanow i eksportow
- lokalnych logow

## Co jest lokalnie

- `samples/`
  - probki robocze i testowe
- `outputs/`
  - cropy, review, OCR/HTR i eksporty
- `models/`
  - modele HTR
- `scripts/`
  - skrypty do preprocessingu, ciecia, review i treningu

## Aktualna sciezka

1. `preprocess_handwritten.py`
2. `split_column_cells.py`
3. `build_cell_review_manifest.py`
4. `build_review_html.py`
5. review i eksport poprawek
6. `import_review_export.py`
7. `build_training_set.py`
8. `run_ketos_finetune.py`

## Trening

Najstabilniejsza sciezka na Windowsie jest teraz taka:

1. zbuduj path-format dataset:
   - `build_training_set.py`
2. skompiluj go do `dataset.arrow`
3. trenuj `ketos` z `-f binary`

Skrypt `run_ketos_finetune.py` robi kroki 2 i 3 sam:

```powershell
python scripts/run_ketos_finetune.py `
  --ground-truth-dir C:\Users\Nocna\source\handwritten-htr\outputs\training-set-context\ground-truth `
  --output-dir C:\Users\Nocna\source\handwritten-htr\outputs\finetune-context `
  --base-model C:\Users\Nocna\AppData\Local\htrmopo\htrmopo\199fb0ec-cf40-50aa-b99a-69ba1f42f0bc\lectaurep_base.mlmodel `
  --epochs 3 `
  --workers 0
```

Uwagi:

- skrypt ustawia `PYTHONUTF8=1` i `PYTHONIOENCODING=utf-8`
- odpala `ketos` z `-v`, co wylacza progress bary powodujace problemy z kodowaniem na Windowsie
- wymusza `-q fixed`, zeby liczba epok byla respektowana
