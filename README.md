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
  - skrypty do preprocessingu, cięcia, review i treningu

## Co potrzebujemy teraz

1. Stabilnego `layout` dla wielu typow stron.
2. Sensownego `review UI` z szybkim oznaczaniem pol.
3. Importu/eksportu poprawek do datasetu.
4. Datasetu z wielu gmin.
5. Pierwszego benchmarku `przed/po` treningu.

## Aktualna sciezka

1. `preprocess_handwritten.py`
2. `split_column_cells.py`
3. `build_cell_review_manifest.py`
4. `build_review_html.py`
5. review i eksport poprawek
6. `build_training_set.py`
7. `run_ketos_finetune.py`
