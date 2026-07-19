import unittest
from pathlib import Path

import cv2
import numpy as np

from bot.perception.turn_owner import (
    DEFAULT_AVATAR_LAYOUT,
    HybridTurnOwnerDetector,
    HybridTurnOwnerConsensus,
    NormalizedRect,
    YellowHighlightDetector,
)
from contracts.interfaces import SeatPosition


SAMPLE_DIR = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "submissions"
    / "2026-06-21_memu_hand_screenshots"
    / "raw"
)


class AvatarRoiTests(unittest.TestCase):
    def test_normalized_rect_scales_to_frame(self) -> None:
        rect = NormalizedRect(0.25, 0.25, 0.5, 0.5).to_rect(1280, 720)
        self.assertEqual((rect.x, rect.y, rect.width, rect.height), (320, 180, 640, 360))

    def test_default_layout_has_all_four_seats(self) -> None:
        self.assertEqual(set(DEFAULT_AVATAR_LAYOUT.rois), set(SeatPosition))


class YellowHighlightDetectorTests(unittest.TestCase):
    def test_detects_active_seat_on_repository_samples(self) -> None:
        detector = YellowHighlightDetector()
        expected_by_file = {
            "1.png": SeatPosition.LEFT,
            "2.png": SeatPosition.SELF,
            "3.png": SeatPosition.TOP,
            "4.png": SeatPosition.RIGHT,
        }
        for filename, expected in expected_by_file.items():
            with self.subTest(filename=filename):
                frame = cv2.imread(str(SAMPLE_DIR / filename))
                self.assertIsNotNone(frame)
                result = detector.detect(frame)
                self.assertEqual(result.owner, expected)
                self.assertGreater(result.confidence, 0.0)

    def test_returns_unknown_when_no_gold_ring_exists(self) -> None:
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        result = YellowHighlightDetector().detect(frame)
        self.assertIsNone(result.owner)
        self.assertEqual(result.confidence, 0.0)


class HybridTurnOwnerDetectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.detector = HybridTurnOwnerDetector()
        self.previous = {seat: 13 for seat in SeatPosition}

    def test_card_count_delta_identifies_actor_and_next_owner(self) -> None:
        current = dict(self.previous)
        current[SeatPosition.RIGHT] = 11
        result = self.detector.card_count_delta(self.previous, current)
        self.assertEqual(result.actor, SeatPosition.RIGHT)
        self.assertEqual(result.expected_next_owner, SeatPosition.SELF)
        self.assertEqual(result.changed_by, 2)

    def test_multiple_count_changes_are_ambiguous(self) -> None:
        current = dict(self.previous)
        current[SeatPosition.LEFT] = 12
        current[SeatPosition.TOP] = 12
        result = self.detector.card_count_delta(self.previous, current)
        self.assertIsNone(result.actor)
        self.assertIsNone(result.expected_next_owner)

    def test_sets_turn_owner_only_when_both_signals_agree(self) -> None:
        frame = cv2.imread(str(SAMPLE_DIR / "2.png"))
        current = dict(self.previous)
        current[SeatPosition.RIGHT] = 12
        result = self.detector.detect(
            frame,
            previous_card_counts=self.previous,
            current_card_counts=current,
        )
        self.assertEqual(result.turn_owner, SeatPosition.SELF)
        self.assertIsNotNone(result.evidence)
        self.assertTrue(result.evidence.signals_agree)

    def test_rejects_turn_owner_when_signals_disagree(self) -> None:
        frame = cv2.imread(str(SAMPLE_DIR / "2.png"))
        current = dict(self.previous)
        current[SeatPosition.SELF] = 12
        result = self.detector.detect(
            frame,
            previous_card_counts=self.previous,
            current_card_counts=current,
        )
        self.assertIsNone(result.turn_owner)
        self.assertIsNotNone(result.evidence)
        self.assertFalse(result.evidence.signals_agree)

    def test_critical_consensus_requires_three_of_four_and_latest(self) -> None:
        frame = cv2.imread(str(SAMPLE_DIR / "2.png"))
        current = dict(self.previous)
        current[SeatPosition.RIGHT] = 12
        agreed = self.detector.detect(
            frame,
            previous_card_counts=self.previous,
            current_card_counts=current,
        )
        conflict_counts = dict(self.previous)
        conflict_counts[SeatPosition.SELF] = 12
        conflict = self.detector.detect(
            frame,
            previous_card_counts=self.previous,
            current_card_counts=conflict_counts,
        )
        consensus = HybridTurnOwnerConsensus()

        self.assertIsNone(consensus.observe("bot-1", agreed).turn_owner)
        self.assertIsNone(consensus.observe("bot-1", agreed).turn_owner)
        committed = consensus.observe("bot-1", agreed)
        self.assertEqual(committed.turn_owner, SeatPosition.SELF)
        self.assertEqual(committed.matching_frames, 3)

        # Even with three matching historical frames, a conflicting latest frame revokes turn.
        revoked = consensus.observe("bot-1", conflict)
        self.assertIsNone(revoked.turn_owner)
        self.assertEqual(revoked.matching_frames, 0)

    def test_critical_consensus_is_isolated_by_bot_id(self) -> None:
        frame = cv2.imread(str(SAMPLE_DIR / "2.png"))
        current = dict(self.previous)
        current[SeatPosition.RIGHT] = 12
        agreed = self.detector.detect(
            frame,
            previous_card_counts=self.previous,
            current_card_counts=current,
        )
        consensus = HybridTurnOwnerConsensus()
        consensus.observe("bot-1", agreed)
        consensus.observe("bot-1", agreed)

        self.assertIsNone(consensus.observe("bot-2", agreed).turn_owner)
        self.assertEqual(consensus.observe("bot-1", agreed).turn_owner, SeatPosition.SELF)


if __name__ == "__main__":
    unittest.main()
