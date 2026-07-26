from __future__ import annotations

import unittest

import numpy as np

from bot.perception.pipeline import PerceptionAdapters, PerceptionPipeline
from bot.perception.turn_owner import HighlightDetection
from bot.runtime.schemas import CaptureSource, FrameEnvelope
from bot.runtime.turn_loop import TurnLoop
from contracts.interfaces import (
    ActionKind,
    ButtonId,
    ButtonState,
    CardZone,
    DetectedCard,
    Rect,
    SeatPosition,
)

HAND = ("3S", "4S", "5S", "6S", "7S")


def make_frame() -> FrameEnvelope:
    return FrameEnvelope.create(
        bot_id="bot-1",
        hwnd=10,
        adb_serial="127.0.0.1:23523",
        image=np.zeros((100, 160, 3), dtype=np.uint8),
        source=CaptureSource.WINDOW_RECT,
        sequence=1,
    )


class Cards:
    """A hand of singles, so the rules engine always has a legal lead."""

    def __init__(self, codes=HAND, table=()) -> None:
        self.codes = codes
        self.table = table

    def detect(self, frame: np.ndarray):
        cards = [
            DetectedCard(code, Rect(20 + 10 * i, 60, 8, 20), CardZone.MY_HAND, 0.95)
            for i, code in enumerate(self.codes)
        ]
        cards += [
            DetectedCard(code, Rect(20 + 10 * i, 20, 8, 20), CardZone.TABLE, 0.95)
            for i, code in enumerate(self.table)
        ]
        return cards


class Buttons:
    def __init__(self, *states: ButtonState) -> None:
        self.states = states

    def detect(self, frame: np.ndarray):
        return list(self.states)


def play_button(enabled: bool = True) -> ButtonState:
    return ButtonState(ButtonId.PLAY, "Đánh", Rect(40, 40, 20, 10), is_enabled=enabled, confidence=0.9)


def cancel_button() -> ButtonState:
    return ButtonState(ButtonId.CANCEL_AUTO, "Hủy tự động", Rect(60, 80, 30, 10), confidence=0.99)


class Highlight:
    def __init__(self, owner: SeatPosition | None) -> None:
        self.owner = owner

    def detect(self, frame: np.ndarray) -> HighlightDetection:
        roi = Rect(1, 1, 10, 10) if self.owner is not None else None
        return HighlightDetection(self.owner, 0.9 if self.owner is not None else 0.0, roi, {})


def build(owner, buttons, cards=None) -> TurnLoop:
    return TurnLoop(
        PerceptionPipeline(PerceptionAdapters(cards=cards or Cards(), buttons=buttons)),
        highlight=Highlight(owner),
    )


class TurnLoopTests(unittest.TestCase):
    def test_it_acts_when_both_turn_signals_agree(self) -> None:
        outcome = build(SeatPosition.SELF, Buttons(play_button())).step(make_frame())
        self.assertTrue(outcome.is_my_turn)
        self.assertEqual(outcome.decision["action"], ActionKind.PLAY.value)
        self.assertIsNotNone(outcome.plan)
        self.assertTrue(set(outcome.plan.cards) <= set(HAND))

    def test_the_highlight_alone_is_not_enough(self) -> None:
        """The gold ring reads SELF on 5 of 582 frames where no action button is
        shown, so acting on it alone would act off-turn."""
        outcome = build(SeatPosition.SELF, Buttons()).step(make_frame())
        self.assertFalse(outcome.is_my_turn)
        self.assertEqual(outcome.decision["reason"], "not_my_turn")
        self.assertIsNone(outcome.plan)

    def test_an_undecided_ring_does_not_forfeit_the_turn(self) -> None:
        """The ring is undecided on 57 of the 165 frames that show an action
        button. Requiring it would forfeit 35% of the bot's turns, and a
        forfeited turn is auto-played - the failure this loop exists to prevent.
        """
        outcome = build(None, Buttons(play_button())).step(make_frame())
        self.assertTrue(outcome.is_my_turn)
        self.assertEqual(outcome.decision["action"], ActionKind.PLAY.value)

    def test_a_ring_on_another_seat_still_vetoes(self) -> None:
        """The one case where the button can be stale or transitional."""
        outcome = build(SeatPosition.LEFT, Buttons(play_button())).step(make_frame())
        self.assertFalse(outcome.is_my_turn)
        self.assertIsNone(outcome.plan)

    def test_auto_play_is_reported_before_any_decision(self) -> None:
        """While the game plays the hand itself, a decision would be acted on by
        nobody; taking the turn back is the only useful move."""
        loop = build(SeatPosition.SELF, Buttons(play_button(), cancel_button()))
        outcome = loop.step(make_frame())
        self.assertIsNotNone(outcome.recovery)
        self.assertIs(outcome.recovery.button_id, ButtonId.CANCEL_AUTO)
        self.assertEqual(outcome.decision["reason"], "auto_play_engaged")
        self.assertIsNone(outcome.plan)

    def test_a_rejected_frame_waits_instead_of_guessing(self) -> None:
        broken = FrameEnvelope.create(
            bot_id="bot-1", hwnd=1, adb_serial="s", image=np.zeros((4, 4), dtype=np.uint8),
            source=CaptureSource.WINDOW_RECT, sequence=1,
        )
        outcome = build(SeatPosition.SELF, Buttons(play_button())).step(broken)
        self.assertEqual(outcome.decision["reason"], "frame_rejected")
        self.assertIsNone(outcome.snapshot)
        self.assertIsNone(outcome.plan)

    def test_a_response_is_planned_before_the_play_button_appears(self) -> None:
        """The game shows only "Bỏ Lượt" until a legal selection exists, so a
        response has to be planned without "Đánh" on screen. The executor looks
        for it again after the cards are selected."""
        outcome = build(
            SeatPosition.SELF,
            Buttons(ButtonState(ButtonId.PASS, "Bỏ Lượt", Rect(10, 40, 20, 10), confidence=0.9)),
            cards=Cards(codes=("5S",), table=("4S",)),
        ).step(make_frame())
        self.assertEqual(outcome.decision["action"], ActionKind.PLAY.value)
        self.assertIsNotNone(outcome.plan)
        self.assertEqual(outcome.plan.cards, ("5S",))

    def test_it_waits_when_the_plan_cannot_be_built(self) -> None:
        """A pass needs its button; without one there is nothing to press."""
        outcome = build(
            SeatPosition.SELF,
            Buttons(play_button()),
            cards=Cards(codes=("3S",), table=("4S",)),
        ).step(make_frame())
        self.assertEqual(outcome.decision["action"], ActionKind.WAIT.value)
        self.assertIn("unplannable", outcome.decision["reason"])
        self.assertIsNone(outcome.plan)

    def test_the_played_cards_are_always_cards_the_hand_holds(self) -> None:
        outcome = build(SeatPosition.SELF, Buttons(play_button())).step(make_frame())
        held = {c.code for c in outcome.snapshot.cards if c.zone is CardZone.MY_HAND}
        self.assertEqual(set(outcome.plan.cards) - held, set())


if __name__ == "__main__":
    unittest.main()


class SelectedCardExecutionTests(unittest.TestCase):
    """A card already selected must not be tapped again."""

    class Recorder:
        def __init__(self) -> None:
            self.taps: list[tuple[int, int]] = []

        def tap(self, x: int, y: int, *, timeout: int = 10) -> str:
            self.taps.append((x, y))
            return "ok"

    def test_an_already_selected_card_is_not_re_tapped(self) -> None:
        """Tapping is a toggle. Re-tapping a selected card deselects it, and the
        turn loops until the clock runs out - observed live, twelve times on the
        same card."""
        from bot.actions.action_pipeline import ActionTapExecutor
        from contracts.interfaces import ActionPlan, PerceptionSnapshot

        snapshot = PerceptionSnapshot(
            bot_id="bot-1", frame_id="f1", frame_ts=1, confidence=0.9,
            cards=(
                DetectedCard("5S", Rect(10, 460, 20, 40), CardZone.SELECTED, 0.9),
                DetectedCard("6S", Rect(40, 520, 20, 40), CardZone.MY_HAND, 0.9),
            ),
            buttons=(play_button(),),
        )
        plan = ActionPlan(kind=ActionKind.PLAY, cards=("5S", "6S"), target_button=ButtonId.PLAY)
        recorder = self.Recorder()
        taps = ActionTapExecutor(recorder, sleep=lambda _s: None).execute(plan, snapshot)
        # 6S is tapped to select it, 5S is skipped, then the action button.
        self.assertEqual([t.target for t in taps], ["6S", str(ButtonId.PLAY)])
