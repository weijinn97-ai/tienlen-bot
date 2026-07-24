"""Small, dependency-light helpers for the launcher live preview."""

from __future__ import annotations

import numpy as np


def frame_to_ppm(frame: np.ndarray) -> bytes:
    """Convert a BGR uint8 frame to a Tk-compatible binary PPM image."""
    if not isinstance(frame, np.ndarray) or frame.dtype != np.uint8:
        raise ValueError("preview frame must be a uint8 numpy array")
    if frame.ndim != 3 or frame.shape[2] != 3:
        raise ValueError("preview frame must have shape [height, width, 3]")
    height, width = frame.shape[:2]
    if width <= 0 or height <= 0:
        raise ValueError("preview frame dimensions must be positive")
    rgb = np.ascontiguousarray(frame[:, :, ::-1])
    return f"P6\n{width} {height}\n255\n".encode("ascii") + rgb.tobytes()
