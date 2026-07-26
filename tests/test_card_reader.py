from __future__ import annotations

import unittest

import cv2
import numpy as np

from bot.perception.card_reader import (
    FRAME_SHAPE,
    GLYPH_X,
    RANK_Y,
    SUIT_Y,
    CardReader,
    CardReaderError,
)
from contracts.interfaces import CardZone

CARD_W, CARD_H = 96, 127
BLACK_INK = (30, 30, 30)
RED_INK = (40, 40, 200)
RED_SUITS = {"D", "H"}


def _paste_glyph(frame, template, x0, y0, x1, y1, colour):
    """Draw a normalised glyph into a window, leaving a margin so the reader's
    ink-bounding-box crop reproduces the template shape."""
    pad_x, pad_y = 6, 4
    w = max(8, (x1 - x0) - 2 * pad_x)
    h = max(8, (y1 - y0) - 2 * pad_y)
    mask = cv2.resize(template, (w, h), interpolation=cv2.INTER_NEAREST) > 0.5
    region = frame[y0 + pad_y : y0 + pad_y + h, x0 + pad_x : x0 + pad_x + w]
    region[mask] = colour


def render_frame(cards, origin=(400, 30), stride=110):
    """Render a synthetic 1280x720 frame containing the given table cards.

    Templates ship with the module, so rendering from them and reading the card
    back is a genuine round trip rather than a fixture baked by hand.
    """
    reader = CardReader()
    frame = np.zeros(FRAME_SHAPE, dtype=np.uint8)
    x, y = origin
    for code in cards:
        rank, suit = code[:-1], code[-1]
        frame[y : y + CARD_H, x : x + CARD_W] = 255
        rx0 = x + int(CARD_H * GLYPH_X[0])
        rx1 = x + min(CARD_W, int(CARD_H * GLYPH_X[1]))
        _paste_glyph(
            frame, reader._ranks[rank],
            rx0, y + int(CARD_H * RANK_Y[0]), rx1, y + int(CARD_H * RANK_Y[1]),
            BLACK_INK,
        )
        _paste_glyph(
            frame, reader._suits[suit],
            rx0, y + int(CARD_H * SUIT_Y[0]), rx1, y + int(CARD_H * SUIT_Y[1]),
            RED_INK if suit in RED_SUITS else BLACK_INK,
        )
        x += stride
    return frame


class CardReaderHappyPathTests(unittest.TestCase):
    def setUp(self) -> None:
        self.reader = CardReader()

    def test_reads_rendered_cards_back(self) -> None:
        codes = ["3S", "10C", "KH", "AD"]
        cards = self.reader.detect(render_frame(codes))
        self.assertEqual([card.code for card in cards], codes)

    def test_every_card_is_reported_in_the_table_zone(self) -> None:
        cards = self.reader.detect(render_frame(["4C", "5H"]))
        self.assertTrue(cards)
        self.assertTrue(all(card.zone is CardZone.TABLE for card in cards))

    def test_confidence_is_within_the_contract_range(self) -> None:
        cards = self.reader.detect(render_frame(["7D", "JS"]))
        self.assertTrue(cards)
        for card in cards:
            self.assertGreaterEqual(card.confidence, 0.0)
            self.assertLessEqual(card.confidence, 1.0)

    def test_roi_encloses_the_rendered_card(self) -> None:
        frame = render_frame(["QS"], origin=(500, 40))
        card = self.reader.detect(frame)[0]
        self.assertEqual(card.roi.x, 500)
        self.assertEqual(card.roi.y, 40)
        self.assertEqual(card.roi.width, CARD_W)
        self.assertEqual(card.roi.height, CARD_H)

    def test_red_and_black_suits_are_distinguished(self) -> None:
        """Colour is what separates D/H from S/C, so it must survive the round trip."""
        red = self.reader.detect(render_frame(["9H"]))
        black = self.reader.detect(render_frame(["9S"]))
        self.assertEqual([c.code for c in red], ["9H"])
        self.assertEqual([c.code for c in black], ["9S"])

    def test_empty_frame_yields_no_cards(self) -> None:
        self.assertEqual(self.reader.detect(np.zeros(FRAME_SHAPE, dtype=np.uint8)), ())


class CardReaderSafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.reader = CardReader()

    def test_input_frame_is_not_mutated(self) -> None:
        frame = render_frame(["6S", "7H"])
        original = frame.copy()
        self.reader.detect(frame)
        np.testing.assert_array_equal(frame, original)

    def test_wrong_frame_shape_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.reader.detect(np.zeros((480, 640, 3), dtype=np.uint8))

    def test_non_array_input_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.reader.detect([[0, 0, 0]])

    def test_unrecognisable_glyph_is_dropped_not_guessed(self) -> None:
        """A blank card carries no index; guessing one would be worse than silence."""
        frame = np.zeros(FRAME_SHAPE, dtype=np.uint8)
        frame[30 : 30 + CARD_H, 400 : 400 + CARD_W] = 255
        self.assertEqual(self.reader.detect(frame), ())

    def test_noise_card_is_dropped(self) -> None:
        frame = np.zeros(FRAME_SHAPE, dtype=np.uint8)
        frame[30 : 30 + CARD_H, 400 : 400 + CARD_W] = 255
        rng = np.random.default_rng(7)
        frame[35:70, 405:445] = rng.integers(0, 90, (35, 40, 3), dtype=np.uint8)
        for card in self.reader.detect(frame):
            self.fail(f"noise was read as {card.code}")

    def test_missing_template_asset_is_reported(self) -> None:
        with self.assertRaises(CardReaderError):
            CardReader(template_path="does-not-exist.npz")


class CardReaderInvariantTests(unittest.TestCase):
    def setUp(self) -> None:
        self.reader = CardReader()

    def test_no_duplicate_card_codes(self) -> None:
        """The same physical card cannot be on the table twice."""
        frame = render_frame(["8C", "8C", "8C"])
        codes = [card.code for card in self.reader.detect(frame)]
        self.assertEqual(len(codes), len(set(codes)))

    def test_ordering_is_by_position_then_code(self) -> None:
        cards = self.reader.detect(render_frame(["5S", "6H", "7C"]))
        keys = [(card.roi.y, card.roi.x, card.code) for card in cards]
        self.assertEqual(keys, sorted(keys))

    def test_ordering_is_stable_across_runs(self) -> None:
        frame = render_frame(["3S", "4D", "5C"])
        first = [card.code for card in self.reader.detect(frame)]
        for _ in range(3):
            self.assertEqual([card.code for card in self.reader.detect(frame)], first)

    def test_warm_up_is_available_and_changes_nothing(self) -> None:
        frame = render_frame(["JC"])
        before = [c.code for c in self.reader.detect(frame)]
        self.reader.warm_up()
        self.assertEqual([c.code for c in self.reader.detect(frame)], before)


class CardReaderTemplateBankTests(unittest.TestCase):
    def test_bank_holds_the_full_taxonomy(self) -> None:
        reader = CardReader()
        self.assertEqual(len(reader._ranks), 13)
        self.assertEqual(len(reader._suits), 4)
        self.assertEqual(set(reader._suits), {"S", "C", "D", "H"})

    def test_every_rank_round_trips(self) -> None:
        reader = CardReader()
        for rank in reader._ranks:
            code = f"{rank}S"
            cards = reader.detect(render_frame([code]))
            self.assertEqual([c.code for c in cards], [code], f"rank {rank} failed")

    def test_every_suit_round_trips(self) -> None:
        reader = CardReader()
        for suit in reader._suits:
            code = f"9{suit}"
            cards = reader.detect(render_frame([code]))
            self.assertEqual([c.code for c in cards], [code], f"suit {suit} failed")


if __name__ == "__main__":
    unittest.main()
