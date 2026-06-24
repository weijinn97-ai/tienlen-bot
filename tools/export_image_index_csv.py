from __future__ import annotations

import argparse
import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SUBMISSIONS_DIR = ROOT / "data" / "submissions"
DEFAULT_OUTPUT = ROOT / "docs" / "google_sheet_seed" / "08_Image_Index.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Aggregate screenshot batch manifests into one Google Sheet index CSV."
    )
    parser.add_argument(
        "--submissions-dir",
        type=Path,
        default=DEFAULT_SUBMISSIONS_DIR,
        help="Root directory that contains screenshot batches.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="CSV output path for Google Sheet seeding.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows = collect_manifest_rows(args.submissions_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)

    with args.output.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "image_id",
                "batch_name",
                "source_filename",
                "repo_relative_path",
                "original_source_path",
                "file_size_bytes",
                "captured_at",
                "room_id",
                "round_text",
                "visibility_mode",
                "cards_visible_count",
                "cards_visible",
                "label_status",
                "split_status",
                "notes",
            ]
        )
        writer.writerows(rows)

    print(f"Wrote {len(rows)} indexed image row(s) to: {args.output}")
    return 0


def collect_manifest_rows(submissions_dir: Path) -> list[list[str]]:
    rows: list[list[str]] = []
    for manifest_path in sorted(submissions_dir.glob("*/manifest.csv")):
        with manifest_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                rows.append(
                    [
                        row["image_id"],
                        row["batch_name"],
                        row["source_filename"],
                        row["repo_relative_path"],
                        row["original_source_path"],
                        row["file_size_bytes"],
                        row["captured_at"],
                        row["room_id"],
                        row["round_text"],
                        row["visibility_mode"],
                        row["cards_visible_count"],
                        row["cards_visible"],
                        row["label_status"],
                        row["split_status"],
                        row["notes"],
                    ]
                )
    return rows


if __name__ == "__main__":
    raise SystemExit(main())
