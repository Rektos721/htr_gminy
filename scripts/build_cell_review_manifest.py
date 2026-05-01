from __future__ import annotations

import argparse
import csv
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Builds a review manifest for individual cell images.")
    parser.add_argument("--cells-manifest", required=True, type=Path)
    parser.add_argument("--output-manifest", required=True, type=Path)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    cells_manifest = args.cells_manifest.resolve()
    output_manifest = args.output_manifest.resolve()
    output_manifest.parent.mkdir(parents=True, exist_ok=True)
    gt_dir = output_manifest.parent / "cell-transcriptions"
    gt_dir.mkdir(parents=True, exist_ok=True)

    with cells_manifest.open("r", encoding="utf-8", newline="") as in_handle, output_manifest.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as out_handle:
        reader = csv.DictReader(in_handle)
        writer = csv.writer(out_handle)
        writer.writerow(
            [
                "image",
                "source",
                "left",
                "top",
                "right",
                "bottom",
                "ocr_guess",
                "manual_text_path",
                "status",
                "notes",
            ]
        )

        for row in reader:
            cell_image = Path(row["cell_image"])
            text_path = gt_dir / f"{cell_image.stem}.gt.txt"
            if not text_path.exists():
                text_path.write_text("", encoding="utf-8")

            if "row_index" in row and "col_index" in row:
                notes = f"r{int(row['row_index']):03d} c{int(row['col_index']):03d}"
            else:
                notes = f"{row['column_name']} #{row['cell_index']}"

            writer.writerow(
                [
                    str(cell_image),
                    row.get("source", ""),
                    row.get("left", ""),
                    row.get("top", ""),
                    row.get("right", ""),
                    row.get("bottom", ""),
                    "",
                    str(text_path),
                    "todo",
                    notes,
                ]
            )

    print(output_manifest)


if __name__ == "__main__":
    main()
