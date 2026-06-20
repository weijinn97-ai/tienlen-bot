from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import itertools
import time
from typing import Any, Mapping


_FRAME_COUNTER = itertools.count(1)


class CaptureSource(str, Enum):
    WINDOWS_GRAPHICS_CAPTURE = "windows_graphics_capture"
    DESKTOP_DUPLICATION = "desktop_duplication"
    WINDOW_RECT = "window_rect"


class CaptureMode(str, Enum):
    IDLE = "idle"
    TRACKING = "tracking"
    ACTIVE = "active"


@dataclass(frozen=True)
class BotBinding:
    bot_id: str
    hwnd: int
    adb_serial: str
    pid: int
    window_title: str = ""
    identity_fingerprint: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.bot_id.strip():
            raise ValueError("bot_id must not be empty.")
        if self.hwnd <= 0:
            raise ValueError("hwnd must be a positive integer.")
        if not self.adb_serial.strip():
            raise ValueError("adb_serial must not be empty.")
        if self.pid <= 0:
            raise ValueError("pid must be a positive integer.")

    @property
    def identity_key(self) -> tuple[int, str, int]:
        return (self.hwnd, self.adb_serial, self.pid)


@dataclass(frozen=True)
class FrameEnvelope:
    bot_id: str
    frame_id: str
    timestamp_ns: int
    hwnd: int
    adb_serial: str
    image: Any
    source: CaptureSource
    sequence: int
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        *,
        bot_id: str,
        hwnd: int,
        adb_serial: str,
        image: Any,
        source: CaptureSource,
        sequence: int,
        metadata: Mapping[str, Any] | None = None,
    ) -> "FrameEnvelope":
        timestamp_ns = time.monotonic_ns()
        frame_id = f"{bot_id}:{next(_FRAME_COUNTER)}:{timestamp_ns}"
        return cls(
            bot_id=bot_id,
            frame_id=frame_id,
            timestamp_ns=timestamp_ns,
            hwnd=hwnd,
            adb_serial=adb_serial,
            image=image,
            source=source,
            sequence=sequence,
            metadata=metadata or {},
        )
