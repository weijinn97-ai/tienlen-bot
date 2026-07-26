"""Agent-facing console for observing and driving one emulator.

This is a diagnostic and development tool, not the runtime capture path. It uses
`adb exec-out screencap`, which the architecture rules forbid in the hot path;
production capture stays Windows-side and HWND-bound. The tool exists so an
agent can look at what the game is actually showing, compare it with what the
perception stack reads, and confirm a tap lands - without hand-writing adb calls.

    py -3 tools/agent_adb.py devices
    py -3 tools/agent_adb.py shot --out frame.png
    py -3 tools/agent_adb.py read
    py -3 tools/agent_adb.py tap 840 451 --confirm
    py -3 tools/agent_adb.py watch --count 20 --interval 2 --out-dir live

Taps change a live game, so `tap` refuses to run without --confirm.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bot.actions.adb_controller import ADBController
from bot.perception.buttons import load_gameplay_button_detector
from bot.perception.card_reader import CardReader
from bot.perception.turn_owner import YellowHighlightDetector
from contracts.interfaces import ButtonId, CardZone, SeatPosition

BUTTON_TEMPLATES = ROOT / "data" / "templates" / "buttons" / "1280x720"


def list_devices(adb_path: str) -> list[str]:
    output = subprocess.run(
        [adb_path, "devices"], capture_output=True, text=True, timeout=15
    ).stdout
    return [
        line.split("\t", 1)[0]
        for line in output.splitlines()[1:]
        if line.strip() and line.endswith("device")
    ]


def resolve_serial(adb_path: str, requested: str | None) -> str:
    if requested:
        return requested
    devices = list_devices(adb_path)
    if not devices:
        raise SystemExit("Khong tim thay thiet bi adb nao dang ket noi.")
    if len(devices) > 1:
        raise SystemExit(f"Co {len(devices)} thiet bi, hay chon bang --serial: {devices}")
    return devices[0]


def capture(adb_path: str, serial: str, out: Path) -> Path:
    """Capture one frame. Binary-safe: stdout is written without text decoding."""
    out.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [adb_path, "-s", serial, "exec-out", "screencap", "-p"],
        capture_output=True,
        timeout=30,
    )
    if result.returncode != 0 or not result.stdout:
        raise SystemExit(f"screencap that bai: {result.stderr.decode('utf-8', 'replace')[:200]}")
    out.write_bytes(result.stdout)
    return out


def describe(path: Path) -> int:
    import cv2

    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise SystemExit(f"Khong doc duoc anh: {path}")
    print(f"anh: {path}  {image.shape[1]}x{image.shape[0]}")

    reader = CardReader()
    cards = reader.detect(image)
    hand = sorted(
        (c for c in cards if c.zone is CardZone.MY_HAND), key=lambda c: c.roi.x
    )
    table = sorted((c for c in cards if c.zone is CardZone.TABLE), key=lambda c: c.roi.x)
    white = reader._white_mask(image)
    hand_boxes, _components = reader._hand_boxes(image, white)
    print(f"o bai tay tim thay : {len(hand_boxes)}")
    print(f"tay doc duoc  ({len(hand)}): {[c.code for c in hand]}")
    print(f"ban doc duoc  ({len(table)}): {[c.code for c in table]}")

    detector = load_gameplay_button_detector(BUTTON_TEMPLATES)
    visible = [state for state in detector.detect(image) if state.is_visible]
    if visible:
        for state in visible:
            centre = (state.roi.x + state.roi.width // 2, state.roi.y + state.roi.height // 2)
            print(
                f"nut {state.button_id.value:<5} bat={state.is_enabled} "
                f"tam={centre} tin_cay={state.confidence:.2f}"
            )
    else:
        print("nut          : khong thay nut hanh dong nao")

    highlight = YellowHighlightDetector().detect(image)
    owner = highlight.owner.name if highlight.owner is not None else "khong ro"
    print(f"vien vang    : {owner} (tin cay {highlight.confidence:.2f})")

    auto = next((s for s in visible if s.button_id is ButtonId.CANCEL_AUTO), None)
    if auto is not None:
        centre = (auto.roi.x + auto.roi.width // 2, auto.roi.y + auto.roi.height // 2)
        print(f"!! DANG TU DANH - bam Huy tu dong tai {centre} de lay lai luot")
        return 0

    play = next(
        (s for s in visible if s.button_id is ButtonId.PLAY),
        None,
    )
    actionable = [s for s in visible if s.button_id in (ButtonId.PLAY, ButtonId.PASS)]
    my_turn = highlight.owner is SeatPosition.SELF and bool(actionable)
    print(f"=> luot cua bot: {my_turn}" + ("" if play is None else f" (nut Danh bat={play.is_enabled})"))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--adb-path", default="adb")
    parser.add_argument("--serial", default=None)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("devices")

    shot = sub.add_parser("shot")
    shot.add_argument("--out", default="frame.png")

    read = sub.add_parser("read")
    read.add_argument("--image", default=None, help="doc file co san thay vi chup moi")
    read.add_argument("--out", default="frame.png")

    tap = sub.add_parser("tap")
    tap.add_argument("x", type=int)
    tap.add_argument("y", type=int)
    tap.add_argument("--confirm", action="store_true", help="bat buoc: tap thay doi van dang choi")

    watch = sub.add_parser("watch")
    watch.add_argument("--count", type=int, default=10)
    watch.add_argument("--interval", type=float, default=2.0)
    watch.add_argument("--out-dir", default="live")

    args = parser.parse_args()

    if args.command == "devices":
        for serial in list_devices(args.adb_path):
            print(serial)
        return 0

    if args.command == "read" and args.image:
        return describe(Path(args.image))

    serial = resolve_serial(args.adb_path, args.serial)

    if args.command == "shot":
        print(capture(args.adb_path, serial, Path(args.out)))
        return 0

    if args.command == "read":
        return describe(capture(args.adb_path, serial, Path(args.out)))

    if args.command == "tap":
        if not args.confirm:
            raise SystemExit("Tap se thay doi van dang choi. Them --confirm de thuc hien.")
        controller = ADBController(device_id=serial, adb_path=args.adb_path, verify_connection=False)
        controller.tap(args.x, args.y)
        print(f"da tap ({args.x}, {args.y}) tren {serial}")
        return 0

    if args.command == "watch":
        directory = Path(args.out_dir)
        for index in range(args.count):
            path = capture(args.adb_path, serial, directory / f"frame_{index:03d}.png")
            print(path)
            if index + 1 < args.count:
                time.sleep(args.interval)
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
