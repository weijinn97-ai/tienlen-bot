from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

try:
    import mss
except ImportError:  # pragma: no cover - depends on the Windows runtime environment
    mss = None

try:
    import win32gui
except ImportError:  # pragma: no cover - depends on the Windows runtime environment
    win32gui = None

from bot.runtime.schemas import CaptureSource


@dataclass(frozen=True)
class ViewportSpec:
    width: int
    height: int
    anchor: str = "bottom_left"

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("Viewport dimensions must be positive.")
        if self.anchor != "bottom_left":
            raise ValueError("Only the bottom_left viewport anchor is supported.")

    def resolve(self, window_rect: dict[str, int]) -> dict[str, int]:
        if self.width > window_rect["width"] or self.height > window_rect["height"]:
            raise RuntimeError("Configured viewport is larger than the captured window.")
        left = window_rect["left"]
        top = window_rect["bottom"] - self.height
        return {
            "left": left,
            "top": top,
            "right": left + self.width,
            "bottom": window_rect["bottom"],
            "width": self.width,
            "height": self.height,
        }


class WindowsCapture:
    def __init__(
        self,
        *,
        hwnd: int | None = None,
        window_name: str | None = None,
        viewport: ViewportSpec | None = None,
    ) -> None:
        if mss is None or win32gui is None:
            raise RuntimeError(
                "WindowsCapture requires the 'mss' and 'pywin32' packages."
            )
        if hwnd is None and window_name is None:
            raise ValueError("Either hwnd or window_name must be provided.")

        resolved_hwnd = hwnd if hwnd is not None else self.find_window(window_name or "")
        if not resolved_hwnd or not win32gui.IsWindow(resolved_hwnd):
            raise ValueError("Window handle is invalid or no longer exists.")

        self.hwnd = resolved_hwnd
        self.viewport = viewport
        self.source = CaptureSource.WINDOW_RECT
        self._sct = mss.mss()

    @staticmethod
    def find_window(window_name: str) -> int:
        if win32gui is None:
            raise RuntimeError("WindowsCapture requires the 'pywin32' package.")
        hwnd = win32gui.FindWindow(None, window_name)
        if not hwnd:
            raise ValueError(f"Window not found: {window_name}")
        return hwnd

    @staticmethod
    def enumerate_windows(title_substring: str | None = None) -> list[dict[str, Any]]:
        if win32gui is None:
            raise RuntimeError("WindowsCapture requires the 'pywin32' package.")
        windows: list[dict[str, Any]] = []

        def callback(hwnd: int, _: Any) -> None:
            if not win32gui.IsWindowVisible(hwnd):
                return

            title = win32gui.GetWindowText(hwnd)
            if title_substring and title_substring not in title:
                return

            windows.append(
                {
                    "hwnd": hwnd,
                    "title": title,
                    "rect": win32gui.GetWindowRect(hwnd),
                }
            )

        win32gui.EnumWindows(callback, None)
        return windows

    def get_window_rect(self) -> dict[str, int]:
        left, top, right, bottom = win32gui.GetWindowRect(self.hwnd)
        width = right - left
        height = bottom - top
        if width <= 0 or height <= 0:
            raise RuntimeError("Window has invalid dimensions for capture.")

        return {
            "left": left,
            "top": top,
            "right": right,
            "bottom": bottom,
            "width": width,
            "height": height,
        }

    def capture_frame(self) -> np.ndarray:
        rect = self.get_window_rect()
        if self.viewport is not None:
            rect = self.viewport.resolve(rect)
        frame = np.array(
            self._sct.grab(
                {
                    "left": rect["left"],
                    "top": rect["top"],
                    "width": rect["width"],
                    "height": rect["height"],
                }
            ),
            copy=True,
        )
        return frame[:, :, :3]
