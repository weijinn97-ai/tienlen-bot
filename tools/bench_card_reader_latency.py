"""Benchmark the card-detector backbone on whatever device this machine has.

Device selection is per-machine, not hardcoded: CUDA when a usable GPU is
present, otherwise CPU. The plan's acceptance thresholds are stated against a
GTX 1650 reference, so the resolved device is reported alongside every number.

Reports warm-up, p50, p95 and p99 as required by TRAINING_PLAN_FINAL.md section
on latency evidence.
"""
from __future__ import annotations

import argparse
import glob
import json
import statistics
import time
from pathlib import Path

import cv2

IMGSZ = 1280
TURN_BUDGET_MS = 12_000
DEFAULT_FRAME_COUNT = 60

REPO_ROOT = Path(__file__).resolve().parents[1]


def resolve_device() -> tuple[str, dict]:
    """Pick the fastest usable device on this machine and describe it."""
    info: dict = {"torch_version": None, "cuda_available": False}
    try:
        import torch
    except Exception as exc:  # noqa: BLE001
        info["error"] = f"torch import failed: {exc}"
        return "cpu", info

    info["torch_version"] = torch.__version__
    info["cuda_build"] = getattr(torch.version, "cuda", None)
    if torch.cuda.is_available() and torch.cuda.device_count() > 0:
        idx = 0
        props = torch.cuda.get_device_properties(idx)
        info.update(
            {
                "cuda_available": True,
                "gpu_name": props.name,
                "vram_total_mb": round(props.total_memory / 1024**2),
                "compute_capability": f"{props.major}.{props.minor}",
            }
        )
        return f"cuda:{idx}", info
    return "cpu", info


def percentiles(samples_ms: list[float]) -> dict:
    ordered = sorted(samples_ms)
    def at(q: float) -> float:
        return ordered[min(len(ordered) - 1, max(0, int(len(ordered) * q) - 1))]
    return {
        "p50": round(statistics.median(ordered), 1),
        "p95": round(at(0.95), 1),
        "p99": round(at(0.99), 1),
        "max": round(ordered[-1], 1),
        "n": len(ordered),
    }


def bench(device: str, frames, weights: Path) -> dict | None:
    from ultralytics import YOLO

    model = YOLO(str(weights))
    t = time.perf_counter()
    model.predict(frames[0], imgsz=IMGSZ, verbose=False, device=device)
    warmup_ms = (time.perf_counter() - t) * 1000
    for _ in range(3):
        model.predict(frames[0], imgsz=IMGSZ, verbose=False, device=device)

    samples = []
    for frame in frames:
        t = time.perf_counter()
        model.predict(frame, imgsz=IMGSZ, verbose=False, device=device)
        samples.append((time.perf_counter() - t) * 1000)

    result = percentiles(samples)
    result["warmup_ms"] = round(warmup_ms, 1)
    result["device"] = device
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--frames-dir",
        type=Path,
        required=True,
        help="Directory of 1280x720 PNG frames. Raw frames live outside Git.",
    )
    parser.add_argument(
        "--weights", type=Path, default=REPO_ROOT / "yolo11n.pt", help="Detector weights."
    )
    parser.add_argument("--count", type=int, default=DEFAULT_FRAME_COUNT)
    parser.add_argument("--out", type=Path, default=None, help="Where to write latency JSON.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.weights.is_file():
        print(f"Weights not found: {args.weights}")
        return 1
    paths = sorted(glob.glob(str(args.frames_dir / "*.png")))[: args.count]
    if not paths:
        print(f"No PNG frames in {args.frames_dir}")
        return 1

    device, info = resolve_device()
    print("=== Thiet bi duoc chon tu dong ===")
    print(json.dumps(info, indent=2))
    print(f"-> device = {device}\n")

    frames = [cv2.imread(p, cv2.IMREAD_COLOR) for p in paths]
    print(f"Frames: {len(frames)} @ {frames[0].shape[1]}x{frames[0].shape[0]}, imgsz={IMGSZ}\n")

    results = {}
    if info.get("cuda_available"):
        results["gpu"] = bench(device, frames, args.weights)
    results["cpu"] = bench("cpu", frames, args.weights)

    print("=== Ket qua (ms) ===")
    for name, r in results.items():
        print(
            f"{name.upper():<4} warmup={r['warmup_ms']:8.1f}  p50={r['p50']:7.1f}  "
            f"p95={r['p95']:7.1f}  p99={r['p99']:7.1f}  max={r['max']:7.1f}"
        )

    print(f"\n=== So voi ngan sach 1 luot = {TURN_BUDGET_MS} ms ===")
    for name, r in results.items():
        print(f"  {name.upper():<4} p99={r['p99']:7.1f} ms -> {r['p99']/TURN_BUDGET_MS*100:5.2f}% ngan sach")

    if "gpu" in results:
        speedup = results["cpu"]["p95"] / results["gpu"]["p95"]
        print(f"\nGPU nhanh hon CPU: {speedup:.1f}x (p95)")

    out = args.out or (args.frames_dir.parent / "latency.json")
    out.write_text(json.dumps({"device_info": info, "results": results}, indent=2), encoding="utf-8")
    print(f"\nDa ghi: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
