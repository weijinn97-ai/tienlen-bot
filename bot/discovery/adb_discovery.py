from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path
import re
import subprocess
from typing import Iterable


DEFAULT_ADB_PATH = "adb"
DEFAULT_MEMUC_PATH = Path(r"C:\Microvirt\MEmu\memuc.exe")

_ADB_LINE_PATTERN = re.compile(
    r"^(?P<serial>\S+)\s+(?P<state>\S+)(?:\s+(?P<details>.*))?$"
)
_MEMUC_VM_PATTERN = re.compile(
    r"^(?P<index>\d+),(?P<name>.*?),(?P<field3>\d+),(?P<running>[01]),(?P<pid>\d+)$"
)
_MEMUC_SERIAL_PATTERN = re.compile(
    r"(?:already connected to|connected to)\s+(?P<serial>\d{1,3}(?:\.\d{1,3}){3}:\d+)"
)


user32 = ctypes.WinDLL("user32", use_last_error=True)


@dataclass(frozen=True)
class AdbDeviceInfo:
    serial: str
    state: str
    product: str | None = None
    model: str | None = None
    device: str | None = None
    transport_id: str | None = None

    @property
    def host(self) -> str | None:
        if ":" not in self.serial:
            return None
        return self.serial.split(":", 1)[0]

    @property
    def port(self) -> int | None:
        if ":" not in self.serial:
            return None
        _, port = self.serial.rsplit(":", 1)
        try:
            return int(port)
        except ValueError:
            return None


@dataclass(frozen=True)
class MEmuVmInfo:
    index: int
    name: str
    field3: int
    is_running: bool
    process_id: int


@dataclass(frozen=True)
class WindowInfo:
    hwnd: int
    title: str
    process_id: int


@dataclass(frozen=True)
class BindingCandidate:
    vm_index: int
    vm_name: str
    process_id: int
    hwnd: int | None
    window_title: str | None
    adb_serial: str | None
    adb_state: str | None
    android_serial: str | None
    model: str | None
    device: str | None
    product: str | None

    @property
    def display_name(self) -> str:
        return self.vm_name or self.window_title or self.adb_serial or str(self.vm_index)

    def as_row(self) -> list[str]:
        return [
            str(self.vm_index),
            self.vm_name,
            self.adb_serial or "-",
            self.android_serial or "-",
            self.window_title or "-",
            str(self.process_id),
            _format_hwnd(self.hwnd),
            self.model or "-",
            self.adb_state or "-",
        ]

    def as_binding_stub(self) -> str:
        if not self.adb_serial or self.hwnd is None or self.process_id <= 0:
            raise ValueError("Binding stub requires serial, hwnd, and process_id.")

        bot_id = _slugify(self.vm_name) or f"memu-{self.vm_index}"
        window_title = self.window_title or self.vm_name
        return (
            "BotBinding(\n"
            f"    bot_id=\"{bot_id}\",\n"
            f"    hwnd={self.hwnd},\n"
            f"    adb_serial=\"{self.adb_serial}\",\n"
            f"    pid={self.process_id},\n"
            f"    window_title=\"{window_title}\",\n"
            f"    identity_fingerprint=\"{self.vm_name}\",\n"
            ")"
        )


def run_command(command: list[str], *, timeout: int = 20) -> str:
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=True,
    )
    return result.stdout


def parse_adb_devices_output(output: str) -> list[AdbDeviceInfo]:
    devices: list[AdbDeviceInfo] = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("List of devices attached"):
            continue

        match = _ADB_LINE_PATTERN.match(line)
        if not match:
            continue

        details = _parse_adb_details(match.group("details") or "")
        devices.append(
            AdbDeviceInfo(
                serial=match.group("serial"),
                state=match.group("state"),
                product=details.get("product"),
                model=details.get("model"),
                device=details.get("device"),
                transport_id=details.get("transport_id"),
            )
        )
    return devices


def list_adb_devices(adb_path: str = DEFAULT_ADB_PATH) -> list[AdbDeviceInfo]:
    output = run_command([adb_path, "devices", "-l"])
    return parse_adb_devices_output(output)


def parse_memuc_listvms_output(output: str) -> list[MEmuVmInfo]:
    vms: list[MEmuVmInfo] = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        match = _MEMUC_VM_PATTERN.match(line)
        if not match:
            continue

        vms.append(
            MEmuVmInfo(
                index=int(match.group("index")),
                name=match.group("name").strip(),
                field3=int(match.group("field3")),
                is_running=match.group("running") == "1",
                process_id=int(match.group("pid")),
            )
        )
    return vms


def list_memu_vms(memuc_path: Path = DEFAULT_MEMUC_PATH) -> list[MEmuVmInfo]:
    output = run_command([str(memuc_path), "listvms"], timeout=60)
    return parse_memuc_listvms_output(output)


def parse_memuc_adb_shell_output(output: str) -> tuple[str | None, str | None]:
    adb_serial: str | None = None
    payload_lines: list[str] = []

    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        match = _MEMUC_SERIAL_PATTERN.search(line)
        if match:
            adb_serial = match.group("serial")
            continue

        payload_lines.append(line)

    payload = payload_lines[-1] if payload_lines else None
    return adb_serial, payload


def resolve_memu_adb_identity(
    vm_index: int,
    *,
    memuc_path: Path = DEFAULT_MEMUC_PATH,
) -> tuple[str | None, str | None]:
    output = run_command(
        [
            str(memuc_path),
            "adb",
            "-i",
            str(vm_index),
            "shell",
            "getprop",
            "ro.serialno",
        ],
        timeout=30,
    )
    return parse_memuc_adb_shell_output(output)


def enumerate_windows_by_pid(pid: int) -> list[WindowInfo]:
    windows: list[WindowInfo] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def callback(hwnd: int, _lparam: int) -> bool:
        process_id = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
        if process_id.value != pid:
            return True
        if not user32.IsWindowVisible(hwnd):
            return True

        length = user32.GetWindowTextLengthW(hwnd)
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, len(buffer))
        title = buffer.value.strip()
        if not title:
            return True

        windows.append(WindowInfo(hwnd=hwnd, title=title, process_id=pid))
        return True

    user32.EnumWindows(callback, 0)
    return windows


def choose_primary_window(windows: Iterable[WindowInfo]) -> WindowInfo | None:
    ordered = sorted(
        windows,
        key=lambda window: (len(window.title.strip()), window.hwnd),
        reverse=True,
    )
    return ordered[0] if ordered else None


def scan_memu_adb_bindings(
    *,
    adb_path: str = DEFAULT_ADB_PATH,
    memuc_path: Path = DEFAULT_MEMUC_PATH,
    running_only: bool = True,
) -> list[BindingCandidate]:
    adb_devices = {device.serial: device for device in list_adb_devices(adb_path)}
    vms = list_memu_vms(memuc_path)
    if running_only:
        vms = [vm for vm in vms if vm.is_running]

    candidates: list[BindingCandidate] = []
    for vm in vms:
        adb_serial, android_serial = (None, None)
        if vm.is_running:
            try:
                adb_serial, android_serial = resolve_memu_adb_identity(
                    vm.index,
                    memuc_path=memuc_path,
                )
            except subprocess.SubprocessError:
                adb_serial, android_serial = (None, None)

        device = adb_devices.get(adb_serial or "")
        window = choose_primary_window(enumerate_windows_by_pid(vm.process_id))
        candidates.append(
            BindingCandidate(
                vm_index=vm.index,
                vm_name=vm.name,
                process_id=vm.process_id,
                hwnd=window.hwnd if window else None,
                window_title=window.title if window else None,
                adb_serial=adb_serial,
                adb_state=device.state if device else None,
                android_serial=android_serial,
                model=device.model if device else None,
                device=device.device if device else None,
                product=device.product if device else None,
            )
        )

    return sorted(candidates, key=lambda candidate: candidate.vm_index)


def filter_candidates(
    candidates: Iterable[BindingCandidate],
    *,
    vm_index: int | None = None,
    name_contains: str | None = None,
) -> list[BindingCandidate]:
    filtered = list(candidates)
    if vm_index is not None:
        filtered = [candidate for candidate in filtered if candidate.vm_index == vm_index]
    if name_contains:
        needle = name_contains.lower()
        filtered = [
            candidate
            for candidate in filtered
            if needle in candidate.vm_name.lower()
            or needle in (candidate.window_title or "").lower()
        ]
    return filtered


def build_bindings_template(candidates: Iterable[BindingCandidate]) -> str:
    stubs = [
        candidate.as_binding_stub()
        for candidate in candidates
        if candidate.adb_serial and candidate.hwnd is not None and candidate.process_id > 0
    ]
    if not stubs:
        return "# No fully-resolved bindings were found."

    joined = ",\n".join(stubs)
    return "from bot.runtime.schemas import BotBinding\n\nBOT_BINDINGS = [\n" + joined + "\n]\n"


def format_candidates_table(candidates: Iterable[BindingCandidate]) -> str:
    headers = [
        "VM",
        "Instance Name",
        "ADB Serial",
        "Android Serial",
        "Window Title",
        "PID",
        "HWND",
        "Model",
        "State",
    ]
    rows = [candidate.as_row() for candidate in candidates]
    return _format_table(headers, rows)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scan running MEmu instances and map them to exact ADB serials."
    )
    parser.add_argument("--adb-path", default=DEFAULT_ADB_PATH)
    parser.add_argument("--memuc-path", default=str(DEFAULT_MEMUC_PATH))
    parser.add_argument("--all-vms", action="store_true")
    parser.add_argument("--as-bindings", action="store_true")
    parser.add_argument("--serial-only", action="store_true")
    parser.add_argument("--vm-index", type=int)
    parser.add_argument("--name-contains")
    args = parser.parse_args()

    candidates = scan_memu_adb_bindings(
        adb_path=args.adb_path,
        memuc_path=Path(args.memuc_path),
        running_only=not args.all_vms,
    )
    candidates = filter_candidates(
        candidates,
        vm_index=args.vm_index,
        name_contains=args.name_contains,
    )

    if args.serial_only:
        serials = [candidate.adb_serial for candidate in candidates if candidate.adb_serial]
        if len(serials) != 1:
            print("Expected exactly one matching running instance for --serial-only.")
            return 1
        print(serials[0])
    elif args.as_bindings:
        print(build_bindings_template(candidates))
    else:
        print(format_candidates_table(candidates))

    if not candidates:
        return 1
    return 0


def _parse_adb_details(details: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for token in details.split():
        if ":" not in token:
            continue
        key, value = token.split(":", 1)
        parsed[key] = value
    return parsed


def _format_hwnd(hwnd: int | None) -> str:
    if hwnd is None:
        return "-"
    return hex(hwnd)


def _format_table(headers: list[str], rows: list[list[str]]) -> str:
    widths = [len(header) for header in headers]
    for row in rows:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], len(value))

    def render_row(values: list[str]) -> str:
        return " | ".join(value.ljust(widths[index]) for index, value in enumerate(values))

    separator = "-+-".join("-" * width for width in widths)
    rendered = [render_row(headers), separator]
    rendered.extend(render_row(row) for row in rows)
    return "\n".join(rendered)


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return slug


if __name__ == "__main__":
    raise SystemExit(main())
