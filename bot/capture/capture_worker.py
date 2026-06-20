from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from threading import Event, Lock
from typing import Callable

from bot.capture.windows_capture import WindowsCapture
from bot.runtime.schemas import BotBinding, CaptureMode, CaptureSource, FrameEnvelope


@dataclass(frozen=True)
class CaptureProfile:
    idle_fps: float = 1.0
    tracking_fps: float = 3.0
    active_fps: float = 8.0

    def interval_for(self, mode: CaptureMode) -> float:
        fps = {
            CaptureMode.IDLE: self.idle_fps,
            CaptureMode.TRACKING: self.tracking_fps,
            CaptureMode.ACTIVE: self.active_fps,
        }[mode]
        return 1.0 / fps


class LatestFrameBuffer:
    def __init__(self) -> None:
        self._frames: deque[FrameEnvelope] = deque(maxlen=1)
        self._lock = Lock()

    def put(self, frame: FrameEnvelope) -> None:
        with self._lock:
            self._frames.clear()
            self._frames.append(frame)

    def latest(self) -> FrameEnvelope | None:
        with self._lock:
            return self._frames[-1] if self._frames else None


class CaptureWorker:
    def __init__(
        self,
        binding: BotBinding,
        *,
        capture_backend: WindowsCapture | None = None,
        profile: CaptureProfile | None = None,
    ) -> None:
        self.binding = binding
        self.profile = profile or CaptureProfile()
        self.capture_backend = capture_backend or WindowsCapture(hwnd=binding.hwnd)
        self.mode = CaptureMode.IDLE
        self.source = getattr(self.capture_backend, "source", CaptureSource.WINDOW_RECT)
        self.latest_frames = LatestFrameBuffer()
        self._sequence = 0

    def set_mode(self, mode: CaptureMode) -> None:
        self.mode = mode

    def target_interval_seconds(self) -> float:
        return self.profile.interval_for(self.mode)

    def capture_once(self) -> FrameEnvelope:
        self._sequence += 1
        image = self.capture_backend.capture_frame()
        frame = FrameEnvelope.create(
            bot_id=self.binding.bot_id,
            hwnd=self.binding.hwnd,
            adb_serial=self.binding.adb_serial,
            image=image,
            source=self.source,
            sequence=self._sequence,
        )
        self.latest_frames.put(frame)
        return frame

    def run(
        self,
        stop_event: Event,
        on_frame: Callable[[FrameEnvelope], None] | None = None,
    ) -> None:
        while not stop_event.is_set():
            frame = self.capture_once()
            if on_frame is not None:
                on_frame(frame)
            stop_event.wait(self.target_interval_seconds())
