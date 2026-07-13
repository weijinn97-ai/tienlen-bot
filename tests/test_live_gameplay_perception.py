import unittest
from pathlib import Path

import cv2

from bot.perception.buttons import load_gameplay_button_detector
from bot.perception.fan_cards import FanCardTemplateRecognizer
from contracts.interfaces import ButtonId


ROOT = Path(__file__).resolve().parents[1]
TRAIN = ROOT / "data" / "submissions" / "2026-06-21_memu_hand_screenshots"
ROUND1 = ROOT / "data" / "submissions" / "2026-07-13_live_vm203_gameplay" / "raw"
ROUND2 = ROOT / "data" / "submissions" / "2026-07-13_live_vm203_gameplay_round2" / "raw"
TEMPLATES = ROOT / "data" / "templates" / "buttons" / "1280x720"


class LiveGameplayPerceptionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.cards = FanCardTemplateRecognizer.from_submission_batch(TRAIN)
        cls.buttons = load_gameplay_button_detector(TEMPLATES)

    def test_reads_live_hands_at_13_12_and_11_cards(self) -> None:
        cases = (
            (ROUND1 / "live_current.png", ("3D", "5C", "7S", "7D", "9S", "9D", "9H", "JD", "KS", "KC", "KD", "AS", "AC")),
            (ROUND1 / "live_after_play.png", ("3D", "5C", "7D", "9S", "9D", "9H", "JD", "KS", "KC", "KD", "AS", "AC")),
            (ROUND2 / "live_after_second_play.png", ("5C", "7D", "9S", "9D", "9H", "JD", "KS", "KC", "KD", "AS", "AC")),
        )
        for path, expected in cases:
            with self.subTest(path=path.name):
                frame = cv2.imread(str(path))
                actual = tuple(card.code for card in self.cards.detect(frame, len(expected)))
                self.assertEqual(actual, expected)

    def test_play_button_transitions_disabled_enabled_disabled(self) -> None:
        cases = (
            (ROUND1 / "live_current.png", False),
            (ROUND1 / "live_selected.png", True),
            (ROUND1 / "live_after_play.png", False),
        )
        for path, expected_enabled in cases:
            with self.subTest(path=path.name):
                frame = cv2.imread(str(path))
                play = next(
                    button
                    for button in self.buttons.detect(frame)
                    if button.button_id == ButtonId.PLAY
                )
                self.assertEqual(play.is_enabled, expected_enabled)


if __name__ == "__main__":
    unittest.main()
