"""Cross-platform process shutdown helpers used by the launcher."""

from __future__ import annotations

import os
import signal
import subprocess
from typing import Any


def creation_flags() -> int:
    """Create a process group on Windows so CTRL_BREAK can reach the child."""
    if os.name == "nt":
        return getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    return 0


def request_graceful_stop(process: Any) -> str:
    """Ask a running child to stop without killing it immediately."""
    if process.poll() is not None:
        return "already_stopped"

    try:
        if os.name == "nt":
            process.send_signal(getattr(signal, "CTRL_BREAK_EVENT", signal.SIGTERM))
        else:
            process.send_signal(signal.SIGTERM)
        return "signal_sent"
    except (AttributeError, OSError, ValueError):
        process.terminate()
        return "terminate_sent"


def force_stop(process: Any) -> bool:
    """Kill a child only after graceful shutdown has exceeded its deadline."""
    if process.poll() is not None:
        return False
    process.kill()
    return True
