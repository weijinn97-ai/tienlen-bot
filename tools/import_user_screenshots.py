from __future__ import annotations

import argparse
import csv
import hashlib
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SUBMISSIONS_DIR = ROOT / "data" / "submissions"


@dataclass(frozen=True)
class ImportedImage:
    image_id: str
    batch_name: str
    source_filename: str
    repo_relative_path: str
    original_source_path: str
    file_size_bytes: int
    captured_at: str
    sha256: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import user-provided screenshots into a shared repo dataset batch."
    )
    parser.add_argument(
        "--batch-name",
        required=True,
        help="Batch folder name under data/submissions.",
    )
    parser.add_argument(
        "--files",
        nargs="+",
        required=True,
        help="One or more screenshot file paths to import.",
    )
    parser.add_argument(
        "--submissions-dir",
        type=Path,
        default=DEFAULT_SUBMISSIONS_DIR,
        help="Root directory for shared screenshot batches.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    batch_dir = args.submissions_dir / args.batch_name
    raw_dir = batch_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    source_paths = [Path(item).expanduser().resolve() for item in args.files]
    ensure_unique_source_names(source_paths)

    imported_rows: list[ImportedImage] = []
    for index, source_path in enumerate(source_paths, start=1):
        if not source_path.exists():
            raise FileNotFoundError(f"Source file does not exist: {source_path}")
        if source_path.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
            raise ValueError(f"Unsupported file type: {source_path}")

        destination_path = raw_dir / source_path.name
        shutil.copy2(source_path, destination_path)

        imported_rows.append(
            ImportedImage(
                image_id=f"{index:03d}",
                batch_name=args.batch_name,
                source_filename=source_path.name,
                repo_relative_path=relative_to_root(destination_path),
                original_source_path=str(source_path),
                file_size_bytes=destination_path.stat().st_size,
                captured_at=datetime.fromtimestamp(
                    destination_path.stat().st_mtime
                ).isoformat(timespec="seconds"),
                sha256=calculate_sha256(destination_path),
            )
        )

    write_batch_manifest(batch_dir, imported_rows)
    write_batch_readme(batch_dir, imported_rows)
    print(
        f"Imported {len(imported_rows)} screenshot(s) into batch: "
        f"{relative_to_root(batch_dir)}"
    )
    return 0


def ensure_unique_source_names(source_paths: list[Path]) -> None:
    seen: set[str] = set()
    duplicates: list[str] = []
    for source_path in source_paths:
        name = source_path.name.lower()
        if name in seen:
            duplicates.append(source_path.name)
        seen.add(name)
    if duplicates:
        duplicate_text = ", ".join(sorted(set(duplicates)))
        raise ValueError(
            "Duplicate source filenames are not supported in one batch: "
            f"{duplicate_text}"
        )


def calculate_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(65536):
            digest.update(chunk)
    return digest.hexdigest()


def relative_to_root(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def write_batch_manifest(batch_dir: Path, imported_rows: list[ImportedImage]) -> None:
    manifest_path = batch_dir / "manifest.csv"
    with manifest_path.open("w", newline="", encoding="utf-8-sig") as handle:
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
                "sha256",
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
        for row in imported_rows:
            writer.writerow(
                [
                    row.image_id,
                    row.batch_name,
                    row.source_filename,
                    row.repo_relative_path,
                    row.original_source_path,
                    row.file_size_bytes,
                    row.captured_at,
                    row.sha256,
                    "",
                    "",
                    "",
                    "",
                    "",
                    "pending",
                    "raw_only",
                    "",
                ]
            )


def write_batch_readme(batch_dir: Path, imported_rows: list[ImportedImage]) -> None:
    readme_path = batch_dir / "README.md"
    lines = [
        "# Screenshot Batch",
        "",
        f"- Batch: `{batch_dir.name}`",
        f"- Imported images: `{len(imported_rows)}`",
        "- Raw screenshots live in `raw/`.",
        "- Shared metadata lives in `manifest.csv`.",
        "- Agents should update `cards_visible`, `label_status`, and `notes` as work progresses.",
        "",
        "## Files",
        "",
    ]
    for row in imported_rows:
        lines.append(f"- `{row.source_filename}` -> `{row.repo_relative_path}`")
    readme_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
