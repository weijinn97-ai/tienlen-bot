from __future__ import annotations

import ctypes
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

try:
    import win32ui
except ImportError:  # pragma: no cover - depends on the Windows runtime environment
    win32ui = None

try:
    import win32con
except ImportError:  # pragma: no cover - depends on the Windows runtime environment
    win32con = None

from bot.runtime.schemas import CaptureSource

# PrintWindow's PW_RENDERFULLCONTENT. The emulator composites through the GPU,
# and without this flag the call hands back an empty surface.
PW_RENDERFULLCONTENT = 3


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

    def capture_window(self) -> np.ndarray:
        """Capture the window's own content, ignoring what is in front of it.

        `capture_frame` reads the screen at the window's coordinates, so anything
        overlapping the window - or hanging off the edge of the desktop - is
        captured instead of the game. PrintWindow asks the window to redraw
        itself into an off-screen surface, which is both correct under occlusion
        and, measured against `adb exec-out screencap -p`, four times faster:
        33ms against 135ms, and the perception stack read the two identically on
        every frame compared.
        """
        if win32ui is None or win32gui is None:
            raise RuntimeError("capture_window requires the 'pywin32' package.")
        left, top, right, bottom = win32gui.GetClientRect(self.hwnd)
        width, height = right - left, bottom - top
        if width <= 0 or height <= 0:
            raise RuntimeError(
                "Window has no client area to capture; it is probably minimised."
            )

        window_dc = win32gui.GetWindowDC(self.hwnd)
        mfc_dc = win32ui.CreateDCFromHandle(window_dc)
        memory_dc = mfc_dc.CreateCompatibleDC()
        bitmap = win32ui.CreateBitmap()
        try:
            bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
            memory_dc.SelectObject(bitmap)
            if not ctypes.windll.user32.PrintWindow(
                self.hwnd, memory_dc.GetSafeHdc(), PW_RENDERFULLCONTENT
            ):
                raise RuntimeError("PrintWindow failed for this window.")
            info = bitmap.GetInfo()
            pixels = np.frombuffer(bitmap.GetBitmapBits(True), dtype=np.uint8)
            frame = pixels.reshape(info["bmHeight"], info["bmWidth"], 4)[:, :, :3].copy()
        finally:
            win32gui.DeleteObject(bitmap.GetHandle())
            memory_dc.DeleteDC()
            mfc_dc.DeleteDC()
            win32gui.ReleaseDC(self.hwnd, window_dc)
        return frame

    def is_minimised(self) -> bool:
        if win32gui is None:
            return False
        left, top, right, bottom = win32gui.GetClientRect(self.hwnd)
        return right - left <= 0 or bottom - top <= 0

    def restore_without_focus(self) -> bool:
        """Bring a minimised window back without taking the user's focus.

        Measured on this emulator: a minimised window has no client area and
        cannot be captured at all, but a restored one can be captured even when
        it is completely covered by other windows - occluded, the capture still
        tracked a screen change of 37.4/255 that the device also saw, and matched
        the device frame to 0.53/255 afterwards. So restoring is enough; the
        window does not have to be visible, and it need not steal focus.

        A window pushed entirely off the desktop is a different matter: it stops
        redrawing, and the capture freezes on whatever it showed last.
        """
        if win32gui is None or win32con is None:
            return False
        if not self.is_minimised():
            return True
        win32gui.ShowWindow(self.hwnd, win32con.SW_SHOWNOACTIVATE)
        return not self.is_minimised()

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
