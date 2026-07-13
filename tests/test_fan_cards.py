import unittest
from pathlib import Path

import cv2

from bot.perception.fan_cards import FanCardTemplateRecognizer, FanGeometry


ROOT = Path(__file__).resolve().parents[1]
TRAIN = ROOT / "data" / "submissions" / "2026-06-21_memu_hand_screenshots"
LIVE = ROOT / "data" / "submissions" / "2026-07-13_live_vm203_gameplay" / "raw"


class FanCardRecognizerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.recognizer = FanCardTemplateRecognizer.from_submission_batch(TRAIN)

    def test_geometry_tracks_hand_count(self) -> None:
        thirteen = FanGeometry().rois(13)
        twelve = FanGeometry().rois(12)
        self.assertEqual(len(thirteen), 13)
        self.assertEqual(len(twelve), 12)
        self.assertGreater(twelve[0].x, thirteen[0].x)

    def test_exactly_reads_withheld_live_hands(self) -> None:
        cases = {
            "live_current.png": ("3D", "5C", "7S", "7D", "9S", "9D", "9H", "JD", "KS", "KC", "KD", "AS", "AC"),
            "live_after_play.png": ("3D", "5C", "7D", "9S", "9D", "9H", "JD", "KS", "KC", "KD", "AS", "AC"),
        }
        for filename, expected in cases.items():
            with self.subTest(filename=filename):
                frame = cv2.imread(str(LIVE / filename))
                actual = tuple(card.code for card in self.recognizer.detect(frame, len(expected)))
                self.assertEqual(actual, expected)
