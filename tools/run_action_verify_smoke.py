from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bot.actions.adb_controller import ADBController
from bot.actions.verification import PostActionVerifier
from bot.capture.windows_capture import ViewportSpec, WindowsCapture
from contracts.interfaces import Rect, VerifyExpectedChange, VerifySpec


def parse_pair(value: str) -> tuple[int, int]:
    x, y = value.split(",", 1)
    return int(x), int(y)


def parse_rect(value: str) -> Rect:
    x, y, width, height = (int(item) for item in value.split(",", 3))
    return Rect(x, y, width, height)


def main() -> None:
    parser = argparse.ArgumentParser(description="Safe live ADB tap + ROI verify smoke test.")
    parser.add_argument("--hwnd", required=True)
    parser.add_argument("--adb-serial", required=True)
    parser.add_argument("--adb-path", default="adb")
    parser.add_argument("--tap", required=True, help="x,y in Android viewport coordinates")
    parser.add_argument("--verify-roi", required=True, help="x,y,width,height")
    parser.add_argument("--viewport", default="1280x720")
    parser.add_argument("--restore-back", action="store_true")
    parser.add_argument("--confirm-safe-ui", action="store_true", required=True)
    args = parser.parse_args()

    viewport_width, viewport_height = (
        int(item) for item in args.viewport.lower().split("x", 1)
    )
    capture = WindowsCapture(
        hwnd=int(args.hwnd, 0),
        viewport=ViewportSpec(viewport_width, viewport_height),
    )
    controller = ADBController(args.adb_path, args.adb_serial)
    tap_x, tap_y = parse_pair(args.tap)
    before = capture.capture_frame()
    try:
        controller.tap(tap_x, tap_y)
        time.sleep(0.6)
        result = PostActionVerifier().verify(
            before_frame=before,
            spec=VerifySpec(
                roi=parse_rect(args.verify_roi),
                expected_change=VerifyExpectedChange.ROI_CHANGED,
                timeout_ms=1500,
                max_retries=1,
                escalate_to_hand_count=False,
            ),
            capture_frame=capture.capture_frame,
        )
    finally:
        if args.restore_back:
            controller.run(["shell", "input", "keyevent", "4"])

    print(json.dumps({
        "succeeded": result.succeeded,
        "reason": result.reason,
        "attempts": result.attempts,
        "metrics": {
            "mean_absolute_diff": round(result.metrics.mean_absolute_diff, 3),
            "changed_pixel_ratio": round(result.metrics.changed_pixel_ratio, 6),
        } if result.metrics else None,
    }, indent=2))
    raise SystemExit(0 if result.succeeded else 1)


if __name__ == "__main__":
    main()
