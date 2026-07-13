from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import cv2

from bot.perception.fan_cards import FanCardTemplateRecognizer


TRAIN = ROOT / "data" / "submissions" / "2026-06-21_memu_hand_screenshots"
LIVE = ROOT / "data" / "submissions" / "2026-07-13_live_vm203_gameplay" / "raw"
CASES = {
    "live_current.png": ("3D", "5C", "7S", "7D", "9S", "9D", "9H", "JD", "KS", "KC", "KD", "AS", "AC"),
    "live_after_play.png": ("3D", "5C", "7D", "9S", "9D", "9H", "JD", "KS", "KC", "KD", "AS", "AC"),
}


def main() -> None:
    recognizer = FanCardTemplateRecognizer.from_submission_batch(TRAIN)
    total = 0
    correct = 0
    for filename, expected in CASES.items():
        frame = cv2.imread(str(LIVE / filename))
        detections = recognizer.detect(frame, len(expected))
        predicted = tuple(card.code for card in detections)
        matched = sum(left == right for left, right in zip(predicted, expected))
        total += len(expected)
        correct += matched
        print(f"{filename}: {matched}/{len(expected)}")
        print(f"  expected={expected}")
        print(f"  predicted={predicted}")
    recall = correct / total
    print(f"exact_slot_recall={recall:.4f} ({correct}/{total})")
    raise SystemExit(0 if recall >= 0.95 else 1)


if __name__ == "__main__":
    main()
