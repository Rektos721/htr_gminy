from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Imports offline review JSON back into gt files and manifest.")
    parser.add_argument("--review-manifest", required=True, type=Path)
    parser.add_argument("--export-json", required=True, type=Path)
    parser.add_argument("--in-place", action="store_true")
    parser.add_argument("--output-manifest", type=Path, default=None)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    review_manifest = args.review_manifest.resolve()
    export_json = args.export_json.resolve()

    if args.in_place:
        output_manifest = review_manifest
    elif args.output_manifest:
        output_manifest = args.output_manifest.resolve()
    else:
        raise SystemExit("Pass either --in-place or --output-manifest.")

    exported = json.loads(export_json.read_text(encoding="utf-8"))
    by_key: dict[tuple[str, str], dict] = {}
    by_id: dict[int, dict] = {}
    for item in exported:
        key = (str(item.get("image_name", "")), str(item.get("manual_text_path", "")))
        by_key[key] = item
        if "id" in item:
            by_id[int(item["id"])] = item

    rows: list[dict[str, str]] = []
    with review_manifest.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        for idx, row in enumerate(reader):
            item = by_id.get(idx)
            if item is None:
                key = (Path(row["image"]).name, row["manual_text_path"])
                item = by_key.get(key)

            if item is not None:
                text = str(item.get("text", ""))
                status = str(item.get("status", row.get("status", "todo")))
                notes = str(item.get("notes", row.get("notes", "")))
                Path(row["manual_text_path"]).write_text(text, encoding="utf-8")
                row["status"] = status
                row["notes"] = notes

            rows.append(row)

    output_manifest.parent.mkdir(parents=True, exist_ok=True)
    with output_manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(output_manifest)


if __name__ == "__main__":
    main()
