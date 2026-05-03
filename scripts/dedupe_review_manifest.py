from __future__ import annotations

import argparse
import csv
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Deduplicates review items across source variants like *-small.")
    parser.add_argument("--review-manifest", required=True, type=Path)
    parser.add_argument("--output-manifest", required=True, type=Path)
    parser.add_argument("--strict-drop-small", action="store_true")
    return parser


def normalize_source_stem(source: str) -> str:
    stem = Path(source).stem
    if stem.endswith("-small"):
        return stem[: -len("-small")]
    return stem


def is_small_variant(source: str) -> bool:
    return Path(source).stem.endswith("-small")


def preference_key(row: dict[str, str]) -> tuple[int, int, str]:
    stem = Path(row["source"]).stem
    is_small = 1 if stem.endswith("-small") else 0
    width = int(float(row.get("right") or 0)) - int(float(row.get("left") or 0))
    height = int(float(row.get("bottom") or 0)) - int(float(row.get("top") or 0))
    return (is_small, -(width * height), row["image"])


def read_text(path: str) -> str:
    p = Path(path)
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8", errors="ignore")


def merge_rows(rows: list[dict[str, str]]) -> dict[str, str]:
    chosen = sorted(rows, key=preference_key)[0].copy()
    chosen_text = read_text(chosen["manual_text_path"]).strip()

    for row in rows:
        row_text = read_text(row["manual_text_path"]).strip()
        row_status = (row.get("status") or "todo").strip() or "todo"
        chosen_status = (chosen.get("status") or "todo").strip() or "todo"

        if not chosen.get("ocr_guess", "").strip() and row.get("ocr_guess", "").strip():
            chosen["ocr_guess"] = row["ocr_guess"]

        if not chosen_text and row_text:
            chosen_text = row_text

        if chosen_status == "todo" and row_status != "todo":
            chosen["status"] = row_status

        if not (chosen.get("notes") or "").strip() and (row.get("notes") or "").strip():
            chosen["notes"] = row["notes"]

    Path(chosen["manual_text_path"]).write_text(chosen_text, encoding="utf-8")
    return chosen


def main() -> None:
    args = build_parser().parse_args()
    review_manifest = args.review_manifest.resolve()
    output_manifest = args.output_manifest.resolve()

    with review_manifest.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)

    grouped: dict[tuple[str, str], list[dict[str, str]]] = {}
    for row in rows:
        key = (normalize_source_stem(row.get("source", "")), row.get("notes", ""))
        grouped.setdefault(key, []).append(row)

    merged = [merge_rows(group_rows) for _, group_rows in sorted(grouped.items())]

    if args.strict_drop_small:
        normalized_sources: dict[str, set[str]] = {}
        for row in merged:
            normalized_sources.setdefault(normalize_source_stem(row.get("source", "")), set()).add(row.get("source", ""))
        merged = [
            row
            for row in merged
            if not (
                is_small_variant(row.get("source", ""))
                and any(not is_small_variant(src) for src in normalized_sources[normalize_source_stem(row.get("source", ""))])
            )
        ]

    output_manifest.parent.mkdir(parents=True, exist_ok=True)
    with output_manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(merged)

    print(f"input={len(rows)}")
    print(f"output={len(merged)}")
    print(output_manifest)


if __name__ == "__main__":
    main()
