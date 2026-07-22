from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Iterable, Sequence

import cv2
import numpy as np


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
SUIT_ALIASES = {"spades": "S", "clubs": "C", "diamonds": "D", "hearts": "H"}
INVENTORY_FIELDS = (
    "asset_id",
    "relative_path",
    "submission",
    "session_id",
    "match_id",
    "round_id",
    "zone",
    "sha256",
    "phash64",
    "width",
    "height",
    "annotation_path",
    "annotation_status",
    "error",
)
SPLIT_FIELDS = ("asset_id", "relative_path", "group_id", "split", "split_reason")
REVIEW_FIELDS = (
    "asset_id",
    "relative_path",
    "split",
    "annotation_status",
    "review_required",
    "review_reason",
)
DUPLICATE_FIELDS = (
    "duplicate_group_id",
    "asset_id",
    "relative_path",
    "duplicate_kind",
    "minimum_hamming_distance",
)


class InventoryError(RuntimeError):
    pass


class UnionFind:
    def __init__(self, values: Iterable[str]) -> None:
        self.parent = {value: value for value in values}

    def find(self, value: str) -> str:
        parent = self.parent[value]
        if parent != value:
            self.parent[value] = self.find(parent)
        return self.parent[value]

    def union(self, left: str, right: str) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root == right_root:
            return
        first, second = sorted((left_root, right_root))
        self.parent[second] = first


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build deterministic dataset inventory, split and annotation QA reports."
    )
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--phash-threshold", type=int, default=6)
    parser.add_argument("--seed", type=int, default=17)
    return parser.parse_args(argv)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def phash64(image: np.ndarray) -> str:
    if image is None or image.size == 0:
        raise ValueError("Cannot hash an empty image.")
    if image.ndim == 3:
        image = cv2.cvtColor(image[:, :, :3], cv2.COLOR_BGR2GRAY)
    resized = cv2.resize(image, (32, 32), interpolation=cv2.INTER_AREA)
    coefficients = cv2.dct(resized.astype(np.float32))[:8, :8].flatten()
    threshold = float(np.median(coefficients[1:]))
    bits = coefficients > threshold
    value = 0
    for bit in bits:
        value = (value << 1) | int(bit)
    return f"{value:016x}"


def hamming_distance(left: str, right: str) -> int:
    return (int(left, 16) ^ int(right, 16)).bit_count()


def normalize_card_mention(value: str) -> str:
    normalized = value.strip().upper()
    if re.fullmatch(r"(?:10|[2-9JQKA])[SCDH]", normalized):
        return normalized
    legacy = re.fullmatch(
        r"(10|[2-9JQKA])_(SPADES|CLUBS|DIAMONDS|HEARTS)", normalized
    )
    if legacy:
        return legacy.group(1) + SUIT_ALIASES[legacy.group(2).lower()]
    return "UNKNOWN"


def _read_manifest(batch_dir: Path) -> dict[str, dict[str, str]]:
    manifest = batch_dir / "manifest.csv"
    if not manifest.exists():
        return {}
    with manifest.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = csv.DictReader(handle)
        return {
            (row.get("source_filename") or "").strip().lower(): {
                str(key): (value or "").strip() for key, value in row.items() if key
            }
            for row in rows
            if (row.get("source_filename") or "").strip()
        }


def _metadata(row: dict[str, str], submission: str) -> tuple[str, str, str, str]:
    session_id = row.get("session_id") or submission or "UNKNOWN"
    match_id = row.get("match_id") or "UNKNOWN"
    round_id = row.get("round_id") or ""
    if not round_id:
        match = re.match(r"^(\d+/\d+)\b", row.get("round_text", ""))
        round_id = match.group(1) if match else "UNKNOWN"

    explicit_zone = row.get("zone", "").strip().upper()
    if explicit_zone in {"MY_HAND", "TABLE_PLAY", "BUTTON_UI", "OCR_FIELDS"}:
        zone = explicit_zone
    else:
        label_status = row.get("label_status", "").lower()
        cards_visible = row.get("cards_visible", "").strip()
        zone = "MY_HAND" if "hand" in label_status or cards_visible else "UNKNOWN"
    return session_id, match_id, round_id, zone


def _annotation_for(batch_dir: Path, image_path: Path, zone: str) -> tuple[str, str, str]:
    candidates = (
        batch_dir / "labels" / f"{image_path.stem}.txt",
        image_path.with_suffix(".txt"),
    )
    annotation = next((path for path in candidates if path.exists()), None)
    if annotation is None:
        status = "NOT_REQUIRED" if zone in {"BUTTON_UI", "OCR_FIELDS"} else "MISSING"
        return "", status, ""
    error = validate_yolo_annotation(annotation)
    return annotation.as_posix(), "INVALID" if error else "PRESENT", error


def validate_yolo_annotation(path: Path) -> str:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        return f"annotation_read_error:{type(exc).__name__}"
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) != 5:
            return f"line_{line_number}:expected_5_fields"
        try:
            class_id = int(parts[0])
            coordinates = [float(value) for value in parts[1:]]
        except ValueError:
            return f"line_{line_number}:non_numeric_value"
        if not 0 <= class_id < 52:
            return f"line_{line_number}:class_out_of_range"
        if any(value < 0.0 or value > 1.0 for value in coordinates):
            return f"line_{line_number}:coordinate_out_of_range"
        if coordinates[2] <= 0.0 or coordinates[3] <= 0.0:
            return f"line_{line_number}:non_positive_box"
    return ""


def discover_inventory(repo_root: Path) -> tuple[list[dict[str, object]], dict[str, dict[str, str]]]:
    submissions = repo_root / "data" / "submissions"
    rows: list[dict[str, object]] = []
    source_metadata: dict[str, dict[str, str]] = {}
    if not submissions.exists():
        return rows, source_metadata

    for batch_dir in sorted(path for path in submissions.iterdir() if path.is_dir()):
        manifest = _read_manifest(batch_dir)
        raw_dir = batch_dir / "raw"
        if not raw_dir.exists():
            continue
        for image_path in sorted(
            (path for path in raw_dir.iterdir() if path.suffix.lower() in IMAGE_SUFFIXES),
            key=lambda path: path.name.lower(),
        ):
            relative = image_path.relative_to(repo_root).as_posix()
            asset_id = hashlib.sha256(relative.encode("utf-8")).hexdigest()[:16]
            metadata = manifest.get(image_path.name.lower(), {})
            session_id, match_id, round_id, zone = _metadata(metadata, batch_dir.name)
            annotation_path, annotation_status, annotation_error = _annotation_for(
                batch_dir, image_path, zone
            )
            if annotation_path:
                annotation_path = Path(annotation_path).relative_to(repo_root).as_posix()

            digest = sha256_file(image_path)
            image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
            error = annotation_error
            if image is None:
                width = height = 0
                perceptual_hash = ""
                error = ";".join(filter(None, (error, "image_decode_failed")))
            else:
                height, width = image.shape[:2]
                perceptual_hash = phash64(image)

            rows.append(
                {
                    "asset_id": asset_id,
                    "relative_path": relative,
                    "submission": batch_dir.name,
                    "session_id": session_id,
                    "match_id": match_id,
                    "round_id": round_id,
                    "zone": zone,
                    "sha256": digest,
                    "phash64": perceptual_hash,
                    "width": width,
                    "height": height,
                    "annotation_path": annotation_path,
                    "annotation_status": annotation_status,
                    "error": error,
                }
            )
            source_metadata[asset_id] = metadata
    return rows, source_metadata


def build_groups(
    inventory: list[dict[str, object]], phash_threshold: int
) -> tuple[dict[str, str], list[dict[str, object]]]:
    if phash_threshold < 0 or phash_threshold > 64:
        raise ValueError("phash_threshold must be within [0, 64].")
    ids = [str(row["asset_id"]) for row in inventory]
    dedup = UnionFind(ids)
    exact: dict[str, list[str]] = defaultdict(list)
    by_id = {str(row["asset_id"]): row for row in inventory}
    minimum_distance = {asset_id: 64 for asset_id in ids}
    kinds = {asset_id: "UNIQUE" for asset_id in ids}

    for row in inventory:
        exact[str(row["sha256"])].append(str(row["asset_id"]))
    for members in exact.values():
        for member in members[1:]:
            dedup.union(members[0], member)
        if len(members) > 1:
            for member in members:
                kinds[member] = "EXACT"
                minimum_distance[member] = 0

    valid = [row for row in inventory if row["phash64"]]
    for index, left in enumerate(valid):
        for right in valid[index + 1 :]:
            distance = hamming_distance(str(left["phash64"]), str(right["phash64"]))
            left_id = str(left["asset_id"])
            right_id = str(right["asset_id"])
            minimum_distance[left_id] = min(minimum_distance[left_id], distance)
            minimum_distance[right_id] = min(minimum_distance[right_id], distance)
            if distance <= phash_threshold:
                dedup.union(left_id, right_id)
                if kinds[left_id] == "UNIQUE":
                    kinds[left_id] = "NEAR"
                if kinds[right_id] == "UNIQUE":
                    kinds[right_id] = "NEAR"

    components: dict[str, list[str]] = defaultdict(list)
    for asset_id in ids:
        components[dedup.find(asset_id)].append(asset_id)
    group_ids: dict[str, str] = {}
    duplicate_rows: list[dict[str, object]] = []
    for members in sorted((sorted(value) for value in components.values())):
        group_id = "dup-" + hashlib.sha256("|".join(members).encode()).hexdigest()[:12]
        for member in members:
            group_ids[member] = group_id
            duplicate_rows.append(
                {
                    "duplicate_group_id": group_id,
                    "asset_id": member,
                    "relative_path": by_id[member]["relative_path"],
                    "duplicate_kind": kinds[member],
                    "minimum_hamming_distance": (
                        minimum_distance[member] if minimum_distance[member] < 64 else ""
                    ),
                }
            )
    return group_ids, duplicate_rows


def build_split(
    inventory: list[dict[str, object]], duplicate_groups: dict[str, str], seed: int
) -> list[dict[str, object]]:
    ids = [str(row["asset_id"]) for row in inventory]
    boundaries = UnionFind(ids)
    by_duplicate: dict[str, list[str]] = defaultdict(list)
    by_capture: dict[str, list[str]] = defaultdict(list)
    for row in inventory:
        asset_id = str(row["asset_id"])
        by_duplicate[duplicate_groups[asset_id]].append(asset_id)
        session = str(row["session_id"])
        match = str(row["match_id"])
        round_id = str(row["round_id"])
        if "UNKNOWN" in {session, match, round_id}:
            capture_key = f"submission:{row['submission']}"
        else:
            capture_key = f"capture:{session}|{match}|{round_id}"
        by_capture[capture_key].append(asset_id)
    for members in list(by_duplicate.values()) + list(by_capture.values()):
        for member in members[1:]:
            boundaries.union(members[0], member)

    groups: dict[str, list[str]] = defaultdict(list)
    for asset_id in ids:
        groups[boundaries.find(asset_id)].append(asset_id)
    ordered = sorted(
        (sorted(members) for members in groups.values()),
        key=lambda members: hashlib.sha256(
            f"{seed}|{'|'.join(members)}".encode()
        ).hexdigest(),
    )
    total = len(ids)
    targets = {"train": total * 0.70, "val": total * 0.15, "test": total * 0.15}
    counts = Counter({"train": 0, "val": 0, "test": 0})
    assignment: dict[str, str] = {}
    split_order = ("train", "val", "test")
    for index, members in enumerate(ordered):
        if index < len(split_order) and len(ordered) >= len(split_order):
            split = split_order[index]
        else:
            split = max(
                split_order,
                key=lambda name: (targets[name] - counts[name], -split_order.index(name)),
            )
        for member in members:
            assignment[member] = split
        counts[split] += len(members)

    by_id = {str(row["asset_id"]): row for row in inventory}
    output = []
    for asset_id in sorted(ids, key=lambda value: str(by_id[value]["relative_path"])):
        root = boundaries.find(asset_id)
        group_id = "grp-" + hashlib.sha256(
            "|".join(sorted(groups[root])).encode()
        ).hexdigest()[:12]
        output.append(
            {
                "asset_id": asset_id,
                "relative_path": by_id[asset_id]["relative_path"],
                "group_id": group_id,
                "split": assignment[asset_id],
                "split_reason": "capture_boundary_and_duplicate_component",
            }
        )
    return output


def validate_no_leakage(
    inventory: list[dict[str, object]],
    splits: list[dict[str, object]],
    duplicate_groups: dict[str, str],
) -> list[str]:
    split_by_id = {str(row["asset_id"]): str(row["split"]) for row in splits}
    violations: list[str] = []
    duplicate_splits: dict[str, set[str]] = defaultdict(set)
    capture_splits: dict[str, set[str]] = defaultdict(set)
    for row in inventory:
        asset_id = str(row["asset_id"])
        duplicate_splits[duplicate_groups[asset_id]].add(split_by_id[asset_id])
        session = str(row["session_id"])
        match = str(row["match_id"])
        round_id = str(row["round_id"])
        key = (
            f"submission:{row['submission']}"
            if "UNKNOWN" in {session, match, round_id}
            else f"capture:{session}|{match}|{round_id}"
        )
        capture_splits[key].add(split_by_id[asset_id])
    for key, values in sorted(duplicate_splits.items()):
        if len(values) > 1:
            violations.append(f"duplicate_group:{key}:{sorted(values)}")
    for key, values in sorted(capture_splits.items()):
        if len(values) > 1:
            violations.append(f"capture_group:{key}:{sorted(values)}")
    return violations


def build_annotation_review(
    inventory: list[dict[str, object]], splits: list[dict[str, object]], seed: int
) -> list[dict[str, object]]:
    split_by_id = {str(row["asset_id"]): str(row["split"]) for row in splits}
    train = sorted(
        (str(row["asset_id"]) for row in inventory if split_by_id[str(row["asset_id"])] == "train"),
        key=lambda asset_id: hashlib.sha256(f"{seed}|review|{asset_id}".encode()).hexdigest(),
    )
    train_required = set(train[: int(np.ceil(len(train) * 0.20))])
    output = []
    for row in inventory:
        asset_id = str(row["asset_id"])
        split = split_by_id[asset_id]
        required = split in {"val", "test"} or asset_id in train_required
        reason = "all_val_test" if split in {"val", "test"} else (
            "deterministic_20_percent_train" if required else "not_selected"
        )
        output.append(
            {
                "asset_id": asset_id,
                "relative_path": row["relative_path"],
                "split": split,
                "annotation_status": row["annotation_status"],
                "review_required": str(required).lower(),
                "review_reason": reason,
            }
        )
    return sorted(output, key=lambda row: str(row["relative_path"]))


def _write_csv(path: Path, fields: Sequence[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_pipeline(
    repo_root: Path,
    output: Path,
    *,
    phash_threshold: int = 6,
    seed: int = 17,
) -> dict[str, object]:
    repo_root = repo_root.resolve()
    output = output if output.is_absolute() else repo_root / output
    output.mkdir(parents=True, exist_ok=True)
    inventory, source_metadata = discover_inventory(repo_root)
    duplicate_groups, duplicate_rows = build_groups(inventory, phash_threshold)
    splits = build_split(inventory, duplicate_groups, seed)
    violations = validate_no_leakage(inventory, splits, duplicate_groups)
    reviews = build_annotation_review(inventory, splits, seed)

    inventory = sorted(inventory, key=lambda row: str(row["relative_path"]))
    duplicate_rows = sorted(
        duplicate_rows, key=lambda row: (str(row["duplicate_group_id"]), str(row["relative_path"]))
    )
    split_counts = Counter(str(row["split"]) for row in splits)
    annotation_counts = Counter(str(row["annotation_status"]) for row in inventory)
    zone_counts = Counter(str(row["zone"]) for row in inventory)
    submission_counts = Counter(str(row["submission"]) for row in inventory)
    corrupt = sum(bool(row["error"] and "image_decode_failed" in str(row["error"])) for row in inventory)
    duplicate_component_sizes = Counter(duplicate_groups.values())
    exact_groups = len(
        {str(row["duplicate_group_id"]) for row in duplicate_rows if row["duplicate_kind"] == "EXACT"}
    )
    near_groups = len(
        {str(row["duplicate_group_id"]) for row in duplicate_rows if row["duplicate_kind"] == "NEAR"}
    )
    card_mentions = Counter()
    for metadata in source_metadata.values():
        for card in re.split(r"[;,]", metadata.get("cards_visible", "")):
            normalized_card = normalize_card_mention(card)
            if normalized_card != "UNKNOWN":
                card_mentions[normalized_card] += 1

    coverage = {
        "annotation_status": dict(sorted(annotation_counts.items())),
        "class_coverage": {},
        "corrupt_images": corrupt,
        "exact_duplicate_groups": exact_groups,
        "hard_negative_deficit": max(0, 2000 - zone_counts.get("BUTTON_UI", 0)),
        "leakage_violations": violations,
        "manifest_card_mentions": dict(sorted(card_mentions.items())),
        "metadata_unknown": {
            field: sum(str(row[field]) == "UNKNOWN" for row in inventory)
            for field in ("session_id", "match_id", "round_id", "zone")
        },
        "near_duplicate_groups": near_groups,
        "non_unique_duplicate_components": sum(
            size > 1 for size in duplicate_component_sizes.values()
        ),
        "split_counts": dict(sorted(split_counts.items())),
        "submission_counts": dict(sorted(submission_counts.items())),
        "total_images": len(inventory),
        "valid_images": len(inventory) - corrupt,
        "zone_counts": dict(sorted(zone_counts.items())),
    }

    inventory_path = output / "inventory.csv"
    split_path = output / "split_manifest.csv"
    duplicate_path = output / "duplicate_groups.csv"
    review_path = output / "annotation_review.csv"
    coverage_path = output / "coverage_report.json"
    _write_csv(inventory_path, INVENTORY_FIELDS, inventory)
    _write_csv(split_path, SPLIT_FIELDS, splits)
    _write_csv(duplicate_path, DUPLICATE_FIELDS, duplicate_rows)
    _write_csv(review_path, REVIEW_FIELDS, reviews)
    _write_json(coverage_path, coverage)

    report_paths = (inventory_path, split_path, duplicate_path, review_path, coverage_path)
    latest_input_mtime = max(
        (repo_root / str(row["relative_path"])).stat().st_mtime for row in inventory
    ) if inventory else 0
    manifest = {
        "baseline_commit": _git_head(repo_root),
        "command": "tools/build_dataset_inventory.py",
        "generated_at_utc": datetime.fromtimestamp(
            latest_input_mtime, tz=timezone.utc
        ).isoformat(),
        "input_count": len(inventory),
        "phash_threshold": phash_threshold,
        "report_sha256": {
            path.name: sha256_file(path) for path in sorted(report_paths)
        },
        "seed": seed,
    }
    _write_json(output / "run_manifest.json", manifest)
    if violations:
        raise InventoryError("Dataset leakage detected: " + "; ".join(violations))
    return coverage


def _git_head(repo_root: Path) -> str:
    head = repo_root / ".git" / "HEAD"
    if not head.exists():
        return "UNKNOWN"
    value = head.read_text(encoding="utf-8").strip()
    if value.startswith("ref: "):
        ref = repo_root / ".git" / value[5:]
        return ref.read_text(encoding="utf-8").strip() if ref.exists() else "UNKNOWN"
    return value


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        coverage = run_pipeline(
            args.repo_root,
            args.output,
            phash_threshold=args.phash_threshold,
            seed=args.seed,
        )
    except (InventoryError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 2
    print(
        f"Inventory complete: images={coverage['total_images']} "
        f"leakage={len(coverage['leakage_violations'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
