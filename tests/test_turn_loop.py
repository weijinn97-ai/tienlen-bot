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
        """The gold ring reads SELF on 4 of 110 frames where no action button is
        shown, so acting on it alone would act off-turn."""
        outcome = build(SeatPosition.SELF, Buttons()).step(make_frame())
        self.assertFalse(outcome.is_my_turn)
        self.assertEqual(outcome.decision["reason"], "not_my_turn")
        self.assertIsNone(outcome.plan)

    def test_another_seats_turn_never_acts(self) -> None:
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

    def test_it_waits_when_the_plan_cannot_be_built(self) -> None:
        """The rules engine can call a play the screen cannot support: here the
        hand beats the table, so the answer is PLAY, but no "Đánh" button is
        visible. That means the frame moved on, so the answer is a fresh frame."""
        outcome = build(
            SeatPosition.SELF,
            Buttons(ButtonState(ButtonId.PASS, "Bỏ Lượt", Rect(10, 40, 20, 10), confidence=0.9)),
            cards=Cards(codes=("5S",), table=("4S",)),
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
