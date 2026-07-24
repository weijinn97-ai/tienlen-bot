from __future__ import annotations

from datetime import datetime
from pathlib import Path
import signal
import sys
import time
from threading import Event


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bot.actions.adb_controller import ADBController
from bot.discovery.adb_discovery import (
    choose_primary_window,
    enumerate_windows_by_pid,
    filter_candidates,
    scan_memu_adb_bindings,
)

CHECK_INTERVAL_SECONDS = 3
SUMMARY_EVERY_HEARTBEATS = 5


def log(message: str, level: str = "INFO") -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] [{level}] {message}", flush=True)


def display_name(*, vm_name: str | None, window_title: str | None) -> str:
    return window_title or vm_name or "Unknown Emulator"


def should_emit_summary(heartbeat: int) -> bool:
    return heartbeat == 1 or heartbeat % SUMMARY_EVERY_HEARTBEATS == 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--vm-index" not in argv and "--name-contains" not in argv:
        log("Usage: run_bot_session.py --vm-index <index> | --name-contains <text>", "ERROR")
        return 2

    vm_index = None
    name_contains = None
    if "--vm-index" in argv:
        index = argv.index("--vm-index")
        vm_index = int(argv[index + 1])
    if "--name-contains" in argv:
        index = argv.index("--name-contains")
        name_contains = argv[index + 1]

    candidates = filter_candidates(
        scan_memu_adb_bindings(),
        vm_index=vm_index,
        name_contains=name_contains,
    )
    if not candidates:
        log("No matching running emulator instance was found.", "ERROR")
        return 1
    if len(candidates) > 1:
        log("More than one emulator matched. Narrow the selection first.", "ERROR")
        for candidate in candidates:
            log(
                f"Match VM={candidate.vm_index} name={candidate.vm_name} serial={candidate.adb_serial or '-'}",
                "ERROR",
            )
        return 1

    candidate = candidates[0]
    if not candidate.adb_serial:
        log("The selected emulator does not have a resolved ADB serial.", "ERROR")
        return 1

    controller = ADBController(device_id=candidate.adb_serial, verify_connection=False)
    emulator_name = display_name(
        vm_name=candidate.vm_name,
        window_title=candidate.window_title,
    )

    log(
        "Bot session started | "
        f"title='{emulator_name}' | "
        f"vm={candidate.vm_index} | "
        f"pid={candidate.process_id} | "
        f"hwnd={hex(candidate.hwnd) if candidate.hwnd else '-'} | "
        f"adb_serial={candidate.adb_serial} | "
        f"android_serial={candidate.android_serial or '-'} | "
        f"model={candidate.model or '-'}"
    )
    try:
        model_name = controller.run(["shell", "getprop", "ro.product.model"], timeout=8)
        android_version = controller.run(["shell", "getprop", "ro.build.version.release"], timeout=8)
        wm_size = controller.run(["shell", "wm", "size"], timeout=8)
        log(
            "Android info | "
            f"title='{emulator_name}' | "
            f"model={model_name or '-'} | "
            f"version={android_version or '-'} | "
            f"screen={wm_size or '-'}"
        )
    except Exception as exc:
        log(
            f"Android info failed | title='{emulator_name}' | error={exc}",
            "WARN",
        )

    stop_event = Event()

    def request_stop(signum, _frame) -> None:
        log(f"Shutdown requested by signal {signum}; finishing current check.", "INFO")
        stop_event.set()

    signal.signal(signal.SIGINT, request_stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, request_stop)

    heartbeat = 0
    last_window_title = emulator_name
    adb_ok_previous: bool | None = None
    window_ok_previous: bool | None = None

    log(
        "Watchdog started | "
        f"title='{emulator_name}' | "
        f"check_interval={CHECK_INTERVAL_SECONDS}s | "
        f"log_summary_every={SUMMARY_EVERY_HEARTBEATS} checks"
    )

    while not stop_event.is_set():
        heartbeat += 1
        adb_ok = False
        adb_response = "-"
        try:
            response = controller.health_check(timeout=5)
            adb_ok = True
            adb_response = response or "ping"
        except Exception as exc:
            if adb_ok_previous is not False:
                log(
                    "ADB state changed | "
                    f"title='{emulator_name}' | "
                    f"adb=failed | error={exc}",
                    "ERROR",
                )
            elif should_emit_summary(heartbeat):
                log(
                    "Watchdog summary | "
                    f"title='{emulator_name}' | "
                    "adb=failed | "
                    f"window={'ok' if window_ok_previous else 'missing'} | "
                    f"heartbeat={heartbeat}",
                    "ERROR",
                )

        windows = enumerate_windows_by_pid(candidate.process_id)
        primary = choose_primary_window(windows)
        window_ok = primary is not None
        if primary is None:
            if window_ok_previous is not False:
                log(
                    "Window state changed | "
                    f"title='{emulator_name}' | "
                    f"window=missing | pid={candidate.process_id}",
                    "WARN",
                )
        else:
            if primary.title != last_window_title:
                log(
                    "Window title changed | "
                    f"expected='{last_window_title or '-'}' | "
                    f"current='{primary.title}' | "
                    f"pid={primary.process_id} | "
                    f"hwnd={hex(primary.hwnd)}",
                    "WARN",
                )
                last_window_title = primary.title
                emulator_name = primary.title
            elif window_ok_previous is False:
                log(
                    "Window state changed | "
                    f"title='{primary.title}' | "
                    f"window=ok | "
                    f"hwnd={hex(primary.hwnd)} | "
                    f"pid={primary.process_id}",
                    "INFO",
                )

        if should_emit_summary(heartbeat):
            current_hwnd = hex(primary.hwnd) if primary is not None else "-"
            current_pid = primary.process_id if primary is not None else candidate.process_id
            log(
                "Watchdog summary | "
                f"title='{emulator_name}' | "
                f"adb={'ok' if adb_ok else 'failed'} | "
                f"window={'ok' if window_ok else 'missing'} | "
                f"heartbeat={heartbeat} | "
                f"hwnd={current_hwnd} | "
                f"pid={current_pid}"
            )

        adb_ok_previous = adb_ok
        window_ok_previous = window_ok

        stop_event.wait(CHECK_INTERVAL_SECONDS)

    log("Bot session stopped gracefully.", "INFO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
