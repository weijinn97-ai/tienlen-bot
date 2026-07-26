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

Pass --hwnd to capture the emulator window instead of asking the device for a
PNG: 33ms against 135ms, and the perception stack reads the two identically. The
window may sit behind every other window on the desktop - occlusion was measured
and does not affect it - but it must not be minimised, because a minimised window
has no client area to redraw, and it must not be pushed entirely off the desktop,
because then it stops redrawing and the capture freezes. A minimised window is
restored without taking focus; pass --no-restore-window to leave it alone and use
ADB instead.

The ADB fallback uses `adb exec-out screencap`, which the architecture rules bar
from the production hot path. This is an operator and development tool; the
runtime capture path stays Windows-side and HWND-bound.
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
from bot.capture.windows_capture import WindowsCapture
from bot.perception.buttons import load_gameplay_button_detector
from bot.perception.card_reader import CardReader
from bot.perception.pipeline import PerceptionAdapters, PerceptionPipeline
from bot.runtime.schemas import CaptureSource, FrameEnvelope
from bot.runtime.turn_loop import TurnLoop
from contracts.interfaces import ActionKind, ButtonId, CardZone

BUTTON_TEMPLATES = ROOT / "data" / "templates" / "buttons" / "1280x720"
FRAME_SHAPE = (720, 1280, 3)

# A tap that registered changed at least 19.8% of the card's pixels across the 22
# deliberate taps measured; an untouched region changed none. 10% sits clear of
# both.
TAP_CHANGE_FRACTION = 0.10
TAP_CHANGE_INTENSITY = 40

# How long to let the game act on a play before deciding it was refused.
REFUSAL_CHECK_SECONDS = 0.6


def log(message: str, level: str = "INFO") -> None:
    now = datetime.now().strftime("%H:%M:%S")
    print(f"[{now}] [{level}] {message}", flush=True)


class Screen:
    """One emulator, captured on demand, by whichever route is available.

    Asking the device for a PNG costs 135ms - more than the whole rest of the
    cycle put together. Capturing the emulator window directly costs 33ms and the
    perception stack read the two identically on every frame compared, so the
    window is preferred and the device is the fallback.

    The window route needs the emulator restored: PrintWindow reports a zero-sized
    client area for a minimised window, and there is nothing to redraw. Minimise
    the emulator and this quietly drops back to ADB, four times slower.
    """

    def __init__(
        self,
        adb_path: str,
        serial: str,
        hwnd: int | None = None,
        *,
        restore_window: bool = True,
    ) -> None:
        self.adb_path = adb_path
        self.serial = serial
        self.restore_window = restore_window
        self.window: WindowsCapture | None = None
        self.viewport: tuple[int, int, int, int] | None = None
        # The frame the current decision was made on. Tap confirmation compares
        # against this, so it must be set before any tap is sent.
        self.reference: np.ndarray | None = None
        if hwnd is not None:
            self._prepare_window(hwnd)

    def _prepare_window(self, hwnd: int) -> None:
        """Find where the game sits inside the window, using one device frame."""
        try:
            capture = WindowsCapture(hwnd=hwnd)
            if self.restore_window and capture.is_minimised():
                capture.restore_without_focus()
                time.sleep(0.5)
            window = capture.capture_window()
        except Exception as exc:
            log(f"khong dung duoc duong chup cua so ({exc}); quay ve ADB", "WARN")
            return
        device = self.grab_device()
        if device is None:
            log("khong lay duoc khung ADB de can chuan; quay ve ADB", "WARN")
            return
        best = None
        for width in range(900, window.shape[1] + 1, 4):
            height = round(width * device.shape[0] / device.shape[1])
            if height > window.shape[0]:
                continue
            needle = cv2.resize(device, (width, height), interpolation=cv2.INTER_AREA)
            _, score, _, location = cv2.minMaxLoc(
                cv2.matchTemplate(window, needle, cv2.TM_CCOEFF_NORMED)
            )
            if best is None or score > best[0]:
                best = (score, location[0], location[1], width, height)
        if best is None or best[0] < 0.85:
            log(f"can chuan cua so khong dat (diem {0 if best is None else best[0]:.2f}); "
                "quay ve ADB", "WARN")
            return
        score, x, y, width, height = best
        self.window = capture
        self.viewport = (x, y, width, height)
        log(f"chup qua cua so | vung game x={x} y={y} {width}x{height} | khop {score:.3f}")

    def grab_device(self) -> np.ndarray | None:
        result = subprocess.run(
            [self.adb_path, "-s", self.serial, "exec-out", "screencap", "-p"],
            capture_output=True,
            timeout=30,
        )
        if result.returncode != 0 or not result.stdout:
            return None
        image = cv2.imdecode(np.frombuffer(result.stdout, np.uint8), cv2.IMREAD_COLOR)
        return image if image is not None and image.shape == FRAME_SHAPE else None

    def grab(self) -> np.ndarray | None:
        if self.window is not None and self.viewport is not None:
            try:
                if self.restore_window and self.window.is_minimised():
                    if self.window.restore_without_focus():
                        log("cua so bi thu nho -> da khoi phuc (khong doat focus)", "WARN")
                    else:
                        log("cua so bi thu nho, khoi phuc that bai; dung ADB", "WARN")
                        return self.grab_device()
                raw = self.window.capture_window()
                x, y, width, height = self.viewport
                cropped = raw[y : y + height, x : x + width]
                if cropped.size:
                    return cv2.resize(
                        cropped, (FRAME_SHAPE[1], FRAME_SHAPE[0]), interpolation=cv2.INTER_AREA
                    )
            except Exception as exc:
                log(f"chup cua so hong ({exc}); quay ve ADB", "WARN")
                self.window = None
        return self.grab_device()


def hand_cell_count(snapshot) -> int:
    """How many cards are in the fan, whether or not the reader could name them."""
    return sum(
        1 for card in snapshot.cards
        if card.zone in (CardZone.MY_HAND, CardZone.SELECTED)
    )


def give_up_turn(controller, outcome) -> None:
    """Clear any selection and pass, so a refused play costs a turn not a round."""
    for card in outcome.snapshot.cards:
        if card.zone is CardZone.SELECTED:
            controller.tap(
                card.roi.x + card.roi.width // 2, card.roi.y + card.roi.height // 2
            )
    passer = next(
        (b for b in outcome.snapshot.buttons
         if b.button_id is ButtonId.PASS and b.is_visible and b.is_enabled),
        None,
    )
    if passer is not None:
        controller.tap(
            passer.roi.x + passer.roi.width // 2, passer.roi.y + passer.roi.height // 2
        )


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
        "--hwnd", type=lambda v: int(v, 0), default=None,
        help="cua so giả lập, de chup nhanh gap 4 lan; bo qua thi dung ADB",
    )
    parser.add_argument(
        "--no-restore-window", action="store_true",
        help="de nguyen cua so bi thu nho va dung ADB, thay vi khoi phuc no",
    )
    parser.add_argument(
        "--dump-repeats", default=None,
        help="thu muc luu khung khi cung mot quyet dinh lap lai, de tim nguyen nhan",
    )
    parser.add_argument(
        "--act", action="store_true",
        help="thuc su bam nut va danh bai; mac dinh chi in ra quyet dinh",
    )
    args = parser.parse_args()

    screen = Screen(
        args.adb_path, args.serial, args.hwnd,
        restore_window=not args.no_restore_window,
    )
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
    def confirm_tap(roi) -> bool:
        """Did the last tap change the card it landed on?

        Selection is a toggle, and detecting which card is currently lifted from
        one frame proved unreliable: on 157 measured hand cells no single
        geometric signal separated the selected card from its neighbours - the
        best caught 3 of 19. What is reliable is the change the tap itself makes.
        Over 22 taps we made deliberately, the tapped card's own region changed
        by at least 19.8% of its pixels, while an untouched region changed none.

        The comparison is against the frame the decision was made on, which was
        taken before any tap. Comparing against a frame grabbed inside this
        function instead would compare two post-tap frames, find them identical,
        and report every tap as failed - which taps the card a second time and
        deselects it. That is exactly the loop this check exists to prevent, and
        it is what the first version of it did.
        """
        reference = screen.reference
        if reference is None:
            return True
        image = screen.grab()
        if image is None:
            return True  # cannot tell; assume it landed rather than tap twice
        patch_a = reference[roi.y : roi.y + roi.height, roi.x : roi.x + roi.width]
        patch_b = image[roi.y : roi.y + roi.height, roi.x : roi.x + roi.width]
        if patch_a.shape != patch_b.shape or patch_a.size == 0:
            return True
        changed = np.abs(patch_b.astype(np.int16) - patch_a.astype(np.int16)).max(axis=2)
        return float((changed > TAP_CHANGE_INTENSITY).mean()) >= TAP_CHANGE_FRACTION

    executor = ActionTapExecutor(
        controller,
        confirm_tap=confirm_tap,
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

    acted = cancelled = read_failures = rounds = refused = 0
    last_signature, repeats = None, 0
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

        # A decision that keeps coming back means the previous attempt did not
        # take. Keeping the frame is the only way to find out why, because the
        # log records what the reader believed, not what was on screen.
        signature = (action, tuple(cards), describe(outcome))
        repeats = repeats + 1 if signature == last_signature else 0
        last_signature = signature
        if args.dump_repeats and repeats in (2, 5, 10):
            directory = Path(args.dump_repeats)
            directory.mkdir(parents=True, exist_ok=True)
            path = directory / f"repeat{repeats:02d}_step{step:03d}.png"
            cv2.imwrite(str(path), image)
            log(f"   lap lai {repeats} lan -> da luu {path.name}", "WARN")

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
        # Counting hand cells is the most dependable measurement available: the
        # boxes are found from the white mask alone, so they survive the reader
        # failing to name the cards. If a play went through, this number drops.
        cells = hand_cell_count(outcome.snapshot)

        screen.reference = image
        try:
            taps = executor.execute(
                outcome.plan, outcome.snapshot, skip_selection=repeated
            )
            acted += 1
            note = " (lap lai: chi bam nut)" if repeated else ""
            log(f"   da bam {len(taps)} lan{note}: {[(t.target, t.x, t.y) for t in taps]}")
        except ValueError as exc:
            log(f"   khong thuc hien duoc: {exc}", "WARN")

        # The game refuses a play that breaks the rules and says so on screen,
        # but it says it in Vietnamese text over the fan; the count is easier to
        # read and means the same thing. A refusal almost always means the table
        # was misread - the bot believed it was leading and was not - so trying
        # the same cards again cannot work, and repeating it is what burned whole
        # rounds. Passing is always legal, ends the turn cleanly, and costs one
        # turn instead of the round.
        if args.act and outcome.plan is not None and outcome.plan.kind is ActionKind.PLAY:
            time.sleep(REFUSAL_CHECK_SECONDS)
            follow = screen.grab()
            if follow is not None:
                later = loop.step(
                    FrameEnvelope.create(
                        bot_id="live", hwnd=0, adb_serial=args.serial, image=follow,
                        source=CaptureSource.WINDOWS_GRAPHICS_CAPTURE, sequence=step,
                    )
                )
                if later.snapshot is not None and hand_cell_count(later.snapshot) >= cells:
                    refused += 1
                    log(f"   nuoc di bi tu choi (van {cells} o bai) -> bo luot", "WARN")
                    give_up_turn(controller, later)

        # No sleep here on purpose. The countdown is already running; if this
        # attempt did not land, the next look should happen inside the same turn.

    log(
        f"Ket thuc | da danh={acted} | bi tu choi={refused} | "
        f"da huy tu dong={cancelled} | van moi={rounds} | khung loi={read_failures}"
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
