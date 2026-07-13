from __future__ import annotations

from pathlib import Path

import cv2


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "submissions" / "2026-07-13_live_vm203_gameplay" / "raw"
OUTPUT = ROOT / "data" / "templates" / "buttons" / "1280x720"


def crop(source_name: str, output_name: str, x: int, y: int, width: int, height: int) -> None:
    image = cv2.imread(str(SOURCE / source_name))
    if image is None:
        raise FileNotFoundError(SOURCE / source_name)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    template = image[y : y + height, x : x + width]
    if template.shape[:2] != (height, width):
        raise RuntimeError(f"Invalid crop for {output_name}")
    cv2.imwrite(str(OUTPUT / output_name), template)


def main() -> None:
    crop("live_current.png", "pass_enabled.png", 370, 375, 199, 70)
    crop("live_current.png", "play_disabled.png", 715, 375, 198, 70)
    crop("live_selected.png", "play_enabled.png", 715, 375, 198, 70)
    print(f"Wrote button templates to {OUTPUT}")


if __name__ == "__main__":
    main()
