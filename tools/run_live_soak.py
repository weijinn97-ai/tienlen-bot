from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bot.capture.windows_capture import ViewportSpec, WindowsCapture
from bot.perception.turn_owner import YellowHighlightDetector


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, round((len(ordered) - 1) * fraction))
    return ordered[index]


def run_soak(hwnd: int, duration: float, fps: float, viewport: ViewportSpec) -> dict:
    capture = WindowsCapture(hwnd=hwnd, viewport=viewport)
    detector = YellowHighlightDetector()
    interval = 1.0 / fps
    deadline = time.monotonic() + duration
    latencies = []
    errors = []
    dimensions = set()
    turn_candidates = {"SELF": 0, "LEFT": 0, "TOP": 0, "RIGHT": 0, "UNKNOWN": 0}
    while time.monotonic() < deadline:
        started = time.perf_counter()
        try:
            frame = capture.capture_frame()
            dimensions.add(f"{frame.shape[1]}x{frame.shape[0]}")
            turn = detector.detect(frame).owner
            turn_candidates[turn.name if turn is not None else "UNKNOWN"] += 1
        except Exception as exc:
            errors.append(f"{type(exc).__name__}: {exc}")
        elapsed = time.perf_counter() - started
        latencies.append(elapsed * 1000)
        time.sleep(max(0.0, interval - elapsed))
    return {
        "hwnd": hex(hwnd),
        "duration_seconds": duration,
        "target_fps": fps,
        "frames": len(latencies),
        "dimensions": sorted(dimensions),
        "capture_latency_ms": {
            "mean": round(statistics.fmean(latencies), 3),
            "p95": round(percentile(latencies, 0.95), 3),
            "max": round(max(latencies), 3),
        },
        "turn_candidates": turn_candidates,
        "errors": errors,
        "passed": not errors and dimensions == {f"{viewport.width}x{viewport.height}"},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only MEmu capture soak test.")
    parser.add_argument("--hwnd", required=True, help="Decimal or 0x-prefixed HWND.")
    parser.add_argument("--duration", type=float, default=30.0)
    parser.add_argument("--fps", type=float, default=8.0)
    parser.add_argument("--viewport", default="1280x720")
    args = parser.parse_args()
    width, height = (int(value) for value in args.viewport.lower().split("x", 1))
    result = run_soak(int(args.hwnd, 0), args.duration, args.fps, ViewportSpec(width, height))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
