"""Run the turn loop against a live emulator.

Dry run by default: it reads the screen, decides, prints the decision, and taps
nothing. `--act` lets it play. That split is deliberate - the loop has never
driven a real game, and watching what it *would* do is the cheapest way to find
out whether it should.

Auto-play recovery follows --act, and that is not an oversight. When a turn times
out the game plays the hand itself, and the "Huy tu dong" button is the only way
back - but taking the turn back and then not playing it just lets the clock run
out and auto-play re-engage, one round poorer. Cancelling is only an improvement
if something is going to play the turn. A dry run reports the state and leaves it
alone.

Capture here is `adb exec-out screencap`, which the architecture rules bar from
the production hot path. This is an operator and development tool; the runtime
capture path stays Windows-side and HWND-bound.
"""
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import signal
import subprocess
import sys
from threading import Event
import time

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bot.actions.action_pipeline import ActionTapExecutor
from bot.actions.adb_controller import ADBController
from bot.perception.buttons import load_gameplay_button_detector
from bot.perception.card_reader import CardReader
from bot.perception.pipeline import PerceptionAdapters, PerceptionPipeline
from bot.runtime.schemas import CaptureSource, FrameEnvelope
from bot.runtime.turn_loop import TurnLoop
from contracts.interfaces import ActionKind, CardZone

BUTTON_TEMPLATES = ROOT / "data" / "templates" / "buttons" / "1280x720"
FRAME_SHAPE = (720, 1280, 3)


def log(message: str, level: str = "INFO") -> None:
    now = datetime.now().strftime("%H:%M:%S")
    print(f"[{now}] [{level}] {message}", flush=True)


class Screen:
    """One emulator, captured on demand."""

    def __init__(self, adb_path: str, serial: str) -> None:
        self.adb_path = adb_path
        self.serial = serial
        self.scratch = ROOT / ".runtime" / "last_frame.png"
        self.scratch.parent.mkdir(parents=True, exist_ok=True)

    def grab(self) -> np.ndarray | None:
        result = subprocess.run(
            [self.adb_path, "-s", self.serial, "exec-out", "screencap", "-p"],
            capture_output=True,
            timeout=30,
        )
        if result.returncode != 0 or not result.stdout:
            return None
        self.scratch.write_bytes(result.stdout)
        image = cv2.imread(str(self.scratch), cv2.IMREAD_COLOR)
        return image if image is not None and image.shape == FRAME_SHAPE else None


def describe(outcome) -> str:
    if outcome.snapshot is None:
        return "khung bi tu choi"
    hand = sorted(
        (c.code for c in outcome.snapshot.cards if c.zone is CardZone.MY_HAND)
    )
    table = sorted(c.code for c in outcome.snapshot.cards if c.zone is CardZone.TABLE)
    return f"tay={hand} ban={table}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--serial", required=True)
    parser.add_argument("--adb-path", default="adb")
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--max-steps", type=int, default=200)
    parser.add_argument(
        "--act", action="store_true",
        help="thuc su bam nut va danh bai; mac dinh chi in ra quyet dinh",
    )
    args = parser.parse_args()

    screen = Screen(args.adb_path, args.serial)
    loop = TurnLoop(
        PerceptionPipeline(
            PerceptionAdapters(
                cards=CardReader(),
                buttons=load_gameplay_button_detector(BUTTON_TEMPLATES),
            )
        )
    )
    controller = ADBController(
        adb_path=args.adb_path, device_id=args.serial, verify_connection=False
    )
    executor = ActionTapExecutor(
        controller,
        # The "Danh" button only lights up once cards are selected, so the plan
        # is built against a frame where it is still dark. Re-reading between the
        # card taps and the button tap is what closes that gap.
        refresh_snapshot=lambda: refresh(screen, loop),
    )

    stop = Event()
    signal.signal(signal.SIGINT, lambda *_: stop.set())

    log(
        f"Bat dau | serial={args.serial} | che_do={'DANH THAT' if args.act else 'CHAY THU'} "
        f"| nhip={args.interval}s | toi_da={args.max_steps} buoc"
    )

    acted = cancelled = read_failures = 0
    for step in range(args.max_steps):
        if stop.is_set():
            break
        image = screen.grab()
        if image is None:
            read_failures += 1
            log("khong chup duoc khung hinh", "WARN")
            time.sleep(args.interval)
            continue

        frame = FrameEnvelope.create(
            bot_id="live", hwnd=0, adb_serial=args.serial, image=image,
            source=CaptureSource.WINDOWS_GRAPHICS_CAPTURE, sequence=step,
        )
        started = time.perf_counter()
        outcome = loop.step(frame)
        elapsed = (time.perf_counter() - started) * 1000

        if outcome.recovery is not None:
            x = outcome.recovery.roi.x + outcome.recovery.roi.width // 2
            y = outcome.recovery.roi.y + outcome.recovery.roi.height // 2
            if args.act:
                log(f"TU DANH dang bat -> bam Huy tu dong tai ({x},{y})", "WARN")
                controller.tap(x, y)
                cancelled += 1
            else:
                log(f"TU DANH dang bat tai ({x},{y}) (chay thu: de nguyen)", "WARN")
            time.sleep(args.interval)
            continue

        if not outcome.is_my_turn:
            time.sleep(args.interval)
            continue

        action = outcome.decision.get("action")
        reason = outcome.decision.get("reason", "")
        cards = outcome.decision.get("cards", [])
        log(f"luot ta ({elapsed:.0f}ms) {describe(outcome)} -> {action} {cards} [{reason}]")

        if outcome.plan is None or outcome.plan.kind is ActionKind.WAIT:
            time.sleep(args.interval)
            continue
        if not args.act:
            log("   (chay thu: khong bam gi)")
            time.sleep(args.interval)
            continue

        try:
            taps = executor.execute(outcome.plan, outcome.snapshot)
            acted += 1
            log(f"   da bam {len(taps)} lan: {[(t.target, t.x, t.y) for t in taps]}")
        except ValueError as exc:
            log(f"   khong thuc hien duoc: {exc}", "WARN")
        time.sleep(args.interval)

    log(
        f"Ket thuc | da danh={acted} | da huy tu dong={cancelled} | "
        f"khung loi={read_failures}"
    )
    return 0


def refresh(screen: Screen, loop: TurnLoop):
    """Re-read the screen so the executor sees the button after selection."""
    image = screen.grab()
    if image is None:
        raise ValueError("khong chup duoc khung hinh de doc lai")
    frame = FrameEnvelope.create(
        bot_id="live", hwnd=0, adb_serial=screen.serial, image=image,
        source=CaptureSource.WINDOWS_GRAPHICS_CAPTURE, sequence=0,
    )
    outcome = loop.step(frame)
    if outcome.snapshot is None:
        raise ValueError("khung doc lai khong hop le")
    return outcome.snapshot


if __name__ == "__main__":
    raise SystemExit(main())
