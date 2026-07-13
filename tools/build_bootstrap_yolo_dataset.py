from __future__ import annotations

import csv
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[1]
SUBMISSIONS = ROOT / "data" / "submissions"
OUTPUT = ROOT / "data" / "yolo_bootstrap"
RANKS = ("3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A", "2")
SUITS = ("S", "C", "D", "H")
CLASS_NAMES = tuple(f"{rank}{suit}" for rank in RANKS for suit in SUITS)
CLASS_IDS = {name: index for index, name in enumerate(CLASS_NAMES)}
LEGACY_SUITS = {"spades": "S", "clubs": "C", "diamonds": "D", "hearts": "H"}


def normalize(card: str) -> str:
    value = card.strip()
    if "_" in value:
        rank, suit = value.rsplit("_", 1)
        return f"{rank.upper()}{LEGACY_SUITS[suit.lower()]}"
    return value.upper()


def split_for(batch: str, image_id: str) -> str:
    if batch == "2026-07-13_live_vm203_gameplay":
        return "test"
    number = int(image_id)
    return "val" if number % 5 == 0 else "train"


def boxes_for(count: int) -> list[tuple[float, float, float, float]]:
    left = 137 + max(0, 13 - count) * 35
    pitch = 70
    top = 505
    width = 76
    height = 210
    return [(left + index * pitch, top, width, height) for index in range(count)]


def main() -> None:
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    rows = []
    for manifest in sorted(SUBMISSIONS.glob("*/manifest.csv")):
        with manifest.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                cards = [normalize(card) for card in row.get("cards_visible", "").split(";") if card]
                if not cards or len(cards) != int(row.get("cards_visible_count") or 0):
                    continue
                if any(card not in CLASS_IDS for card in cards):
                    raise ValueError(f"Unknown card in {manifest}: {cards}")
                rows.append((row, cards))

    for row, cards in rows:
        split = split_for(row["batch_name"], row["image_id"])
        image_source = ROOT / row["repo_relative_path"]
        stem = f"{row['batch_name']}__{Path(row['source_filename']).stem}"
        image_target = OUTPUT / "images" / split / f"{stem}.png"
        label_target = OUTPUT / "labels" / split / f"{stem}.txt"
        image_target.parent.mkdir(parents=True, exist_ok=True)
        label_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(image_source, image_target)
        lines = []
        for card, (x, y, width, height) in zip(cards, boxes_for(len(cards))):
            center_x = (x + width / 2) / 1280
            center_y = (y + height / 2) / 720
            lines.append(
                f"{CLASS_IDS[card]} {center_x:.6f} {center_y:.6f} "
                f"{width / 1280:.6f} {height / 720:.6f}"
            )
        label_target.write_text("\n".join(lines) + "\n", encoding="ascii")

    yaml_lines = [
        f"path: {OUTPUT.as_posix()}",
        "train: images/train",
        "val: images/val",
        "test: images/test",
        f"names: {list(CLASS_NAMES)!r}",
    ]
    (OUTPUT / "dataset.yaml").write_text("\n".join(yaml_lines) + "\n", encoding="utf-8")
    counts = {split: len(list((OUTPUT / "images" / split).glob("*.png"))) for split in ("train", "val", "test")}
    print(f"Built bootstrap dataset at {OUTPUT}: {counts}")


if __name__ == "__main__":
    main()
