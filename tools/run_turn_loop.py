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

Timing is the constraint. Each turn has a 13-second countdown; miss it and the
game plays a legal move for you, and after two misses it takes over entirely and
shows "Huy tu dong". The loop itself costs about 50ms, so the poll interval is
what decides how much of those 13 seconds is left to act in - it defaults to
0.3s, and the sleep is skipped entirely on a turn we are acting on, so a retry
lands inside the same countdown instead of the next one.

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
from contracts.interfaces import ActionKind, ButtonId, CardZone

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
    parser.add_argument("--interval", type=float, default=0.3)
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

    acted = cancelled = read_failures = rounds = 0
    last_signature = None
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

        ready = next(
            (
                button
                for button in (outcome.snapshot.buttons if outcome.snapshot else ())
                if button.button_id is ButtonId.READY and button.is_visible
            ),
            None,
        )
        if ready is not None:
            x = ready.roi.x + ready.roi.width // 2
            y = ready.roi.y + ready.roi.height // 2
            if args.act:
                log(f"het van -> bam Tiep Tuc tai ({x},{y})")
                controller.tap(x, y)
                rounds += 1
            else:
                log(f"het van, thay Tiep Tuc tai ({x},{y}) (chay thu: de nguyen)")
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

        # If the same decision comes back on an unchanged hand, the previous
        # attempt did not land. Re-tapping the cards would toggle a selection
        # that may already be correct, so press the button alone and let the
        # game judge it.
        signature = (tuple(outcome.plan.cards), describe(outcome))
        repeated = signature == last_signature
        last_signature = signature
        try:
            taps = executor.execute(
                outcome.plan, outcome.snapshot, skip_selection=repeated
            )
            acted += 1
            note = " (lap lai: chi bam nut)" if repeated else ""
            log(f"   da bam {len(taps)} lan{note}: {[(t.target, t.x, t.y) for t in taps]}")
        except ValueError as exc:
            log(f"   khong thuc hien duoc: {exc}", "WARN")
        # No sleep here on purpose. The countdown is already running; if this
        # attempt did not land, the next look should happen inside the same turn.

    log(
        f"Ket thuc | da danh={acted} | da huy tu dong={cancelled} | "
        f"van moi={rounds} | khung loi={read_failures}"
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
