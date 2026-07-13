import unittest

import numpy as np

from bot.perception.buttons import ButtonTemplate, TemplateButtonDetector
from bot.perception.turn_owner import NormalizedRect
from bot.perception.yolo_cards import YoloCardConfigurationError, YoloCardDetector
from contracts.interfaces import ButtonId


class FakeModel:
    def __init__(self, names):
        self.names = names


def all_legacy_card_names():
    ranks = ["3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A", "2"]
    suits = ["spades", "clubs", "diamonds", "hearts"]
    pairs = [(rank, suit) for rank in ranks for suit in suits]
    return {index: f"{rank}_{suit}" for index, (rank, suit) in enumerate(pairs)}


class YoloConfigurationTests(unittest.TestCase):
    def test_accepts_exact_52_card_taxonomy(self) -> None:
        detector = YoloCardDetector(
            "unused.pt",
            model_factory=lambda path: FakeModel(all_legacy_card_names()),
        )
        self.assertEqual(len(detector.class_codes), 52)
        self.assertIn("2H", detector.class_codes.values())

    def test_rejects_non_card_model(self) -> None:
        with self.assertRaises(YoloCardConfigurationError):
            YoloCardDetector(
                "unused.pt",
                model_factory=lambda path: FakeModel({0: "person"}),
            )


class ButtonTemplateTests(unittest.TestCase):
    def test_detects_template_inside_search_roi(self) -> None:
        frame = np.zeros((100, 200, 3), dtype=np.uint8)
        pattern = np.zeros((12, 20, 3), dtype=np.uint8)
        pattern[:, ::2] = 255
        pattern[::3, :] = 127
        frame[60:72, 140:160] = pattern
        detector = TemplateButtonDetector(
            (
                ButtonTemplate(
                    ButtonId.PLAY,
                    "play",
                    pattern,
                    NormalizedRect(0.5, 0.4, 0.5, 0.6),
                    threshold=0.95,
                ),
            )
        )
        result = detector.detect(frame)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].button_id, ButtonId.PLAY)
        self.assertEqual((result[0].roi.x, result[0].roi.y), (140, 60))


if __name__ == "__main__":
    unittest.main()
