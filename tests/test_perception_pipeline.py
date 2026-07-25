from __future__ import annotations

import unittest

import numpy as np

from bot.perception.ocr import OcrText
from bot.perception.pipeline import (
    FailureComponent,
    PerceptionAdapters,
    PerceptionPipeline,
)
from bot.perception.turn_owner import CardCountDelta, HighlightDetection, TurnOwnerDetection
from bot.runtime.schemas import CaptureSource, FrameEnvelope
from contracts.interfaces import (
    ButtonId,
    ButtonState,
    CardZone,
    DetectedCard,
    GamePhase,
    Rect,
    SeatPosition,
    TurnOwnerEvidence,
    TurnPrimarySignal,
)


def make_frame(image: np.ndarray | None = None) -> FrameEnvelope:
    return FrameEnvelope.create(
        bot_id="bot-1",
        hwnd=10,
        adb_serial="127.0.0.1:23523",
        image=image if image is not None else np.zeros((100, 160, 3), dtype=np.uint8),
        source=CaptureSource.WINDOW_RECT,
        sequence=3,
        metadata={"bot_id": "bot-1"},
    )


class Cards:
    def __init__(self, card: DetectedCard) -> None:
        self.card = card
        self.received: np.ndarray | None = None

    def detect(self, frame: np.ndarray):
        self.received = frame
        return [self.card]


class Buttons:
    def __init__(self) -> None:
        self.received: np.ndarray | None = None

    def detect(self, frame: np.ndarray):
        self.received = frame
        return [
            ButtonState(
                ButtonId.PLAY, "Play", Rect(40, 80, 20, 10), confidence=0.9
            )
        ]


class Ocr:
    def recognize(self, frame: np.ndarray):
        return {"room": OcrText("room-7", Rect(0, 0, 20, 10), 0.95)}


class Turn:
    def __init__(self, owner: SeatPosition | None) -> None:
        self.owner = owner

    def detect(self, frame: np.ndarray, *, previous_card_counts, current_card_counts):
        evidence = None
        if self.owner is not None:
            evidence = TurnOwnerEvidence(
                primary_signal=TurnPrimarySignal.AVATAR_HIGHLIGHT,
                primary_roi=Rect(1, 1, 10, 10),
                primary_confidence=0.9,
                secondary_confidence=0.9,
                signals_agree=True,
            )
        return TurnOwnerDetection(
            turn_owner=self.owner,
            evidence=evidence,
            primary=HighlightDetection(self.owner, 0.9 if self.owner else 0.0, Rect(1, 1, 10, 10) if self.owner else None, {}),
            secondary=CardCountDelta(SeatPosition.LEFT, self.owner, 0.9 if self.owner else 0.0, 1 if self.owner else 0),
        )


class PerceptionPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original = np.full((100, 160, 3), 7, dtype=np.uint8)
        self.card = DetectedCard("AH", Rect(20, 20, 15, 30), CardZone.MY_HAND, 0.98)
        self.cards = Cards(self.card)
        self.buttons = Buttons()
        self.pipeline = PerceptionPipeline(
            PerceptionAdapters(self.cards, self.buttons, Ocr(), Turn(SeatPosition.SELF))
        )

    def test_happy_path_produces_typed_snapshot_and_sorted_ocr(self) -> None:
        result = self.pipeline.process(
            make_frame(self.original),
            previous_card_counts={SeatPosition.LEFT: 5, SeatPosition.SELF: 4},
            current_card_counts={SeatPosition.LEFT: 4, SeatPosition.SELF: 4},
            game_phase=GamePhase.PLAYING,
            room_id="room-7",
        )

        self.assertTrue(result.ok)
        self.assertIsNotNone(result.snapshot)
        assert result.snapshot is not None
        self.assertEqual(result.snapshot.bot_id, "bot-1")
        self.assertEqual(result.snapshot.cards[0].code, "AH")
        self.assertEqual(result.snapshot.turn_owner, SeatPosition.SELF)
        self.assertEqual(result.ocr_fields[0][0], "room")
        self.assertEqual(result.snapshot.game_phase, GamePhase.PLAYING)

    def test_adapter_receives_copy_and_input_is_not_mutated(self) -> None:
        frame_image = self.original.copy()

        class MutatingCards:
            def detect(self, frame: np.ndarray):
                frame[:, :] = 255
                return ()

        pipeline = PerceptionPipeline(PerceptionAdapters(MutatingCards(), self.buttons))
        pipeline.process(make_frame(frame_image))
        np.testing.assert_array_equal(frame_image, self.original)

    def test_invalid_frame_is_rejected_before_adapters(self) -> None:
        invalid = make_frame(np.zeros((100, 160), dtype=np.uint8))
        result = self.pipeline.process(invalid)

        self.assertIsNone(result.snapshot)
        self.assertEqual(result.failures[0].component, FailureComponent.FRAME)

    def test_button_exception_returns_disabled_safe_buttons(self) -> None:
        class BrokenButtons:
            def detect(self, frame: np.ndarray):
                raise RuntimeError("template failed")

        pipeline = PerceptionPipeline(PerceptionAdapters(self.cards, BrokenButtons()))
        result = pipeline.process(make_frame(self.original))

        self.assertFalse(result.ok)
        self.assertEqual(result.failures[0].component, FailureComponent.BUTTONS)
        assert result.snapshot is not None
        self.assertTrue(result.snapshot.buttons)
        self.assertTrue(all(not button.is_visible and not button.is_enabled for button in result.snapshot.buttons))

    def test_turn_exception_clears_owner_and_records_failure(self) -> None:
        class BrokenTurn:
            def detect(self, frame: np.ndarray, **kwargs):
                raise RuntimeError("turn failed")

        pipeline = PerceptionPipeline(PerceptionAdapters(self.cards, self.buttons, turn=BrokenTurn()))
        result = pipeline.process(
            make_frame(self.original),
            previous_card_counts={SeatPosition.LEFT: 5},
            current_card_counts={SeatPosition.LEFT: 4},
        )

        self.assertFalse(result.ok)
        assert result.snapshot is not None
        self.assertIsNone(result.snapshot.turn_owner)
        self.assertIsNone(result.snapshot.turn_owner_evidence)
        self.assertTrue(any(f.component == FailureComponent.TURN for f in result.failures))

    def test_conflicting_turn_detector_is_safe(self) -> None:
        pipeline = PerceptionPipeline(PerceptionAdapters(self.cards, self.buttons, turn=Turn(None)))
        result = pipeline.process(
            make_frame(self.original),
            previous_card_counts={SeatPosition.LEFT: 5},
            current_card_counts={SeatPosition.LEFT: 4},
        )

        self.assertTrue(result.ok)
        assert result.snapshot is not None
        self.assertIsNone(result.snapshot.turn_owner)

    def test_metadata_identity_mismatch_is_rejected(self) -> None:
        frame = FrameEnvelope.create(
            bot_id="bot-1",
            hwnd=10,
            adb_serial="adb",
            image=self.original,
            source=CaptureSource.WINDOW_RECT,
            sequence=1,
            metadata={"bot_id": "other-bot"},
        )
        result = self.pipeline.process(frame)

        self.assertIsNone(result.snapshot)
        self.assertEqual(result.failures[0].component, FailureComponent.FRAME)


if __name__ == "__main__":
    unittest.main()
