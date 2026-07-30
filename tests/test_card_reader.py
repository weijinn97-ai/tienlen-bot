from __future__ import annotations

import unittest

import cv2
import numpy as np

from bot.perception.card_reader import (
    FRAME_SHAPE,
    HAND_RANK_BOX,
    HAND_SUIT_BOX,
    _suit_by_shape,
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


HAND_W, HAND_H = 155, 205


def render_hand_frame(cards, angle=0.0, origin=(200, 512), stride=140):
    """Render a synthetic fan of hand cards, optionally rotated.

    Hand cards are larger than table cards and tilted, so the reader deskews each
    one before reading. Rendering at a known angle is how that path gets covered
    without shipping raw frames.
    """
    reader = CardReader()
    frame = np.zeros(FRAME_SHAPE, dtype=np.uint8)
    x, y = origin
    for code in cards:
        rank, suit = code[:-1], code[-1]
        card = np.zeros((HAND_H, HAND_W, 3), dtype=np.uint8)
        card[:, :] = 255
        # Paste into the reader's own windows so the fixture cannot drift away
        # from the geometry under test.
        _paste_glyph(card, reader._hand_ranks[rank], *HAND_RANK_BOX, BLACK_INK)
        _paste_glyph(
            card, reader._hand_suits[suit], *HAND_SUIT_BOX,
            RED_INK if suit in RED_SUITS else BLACK_INK,
        )
        if angle:
            matrix = cv2.getRotationMatrix2D((0.0, 0.0), angle, 1.0)
            card = cv2.warpAffine(card, matrix, (HAND_W, HAND_H), flags=cv2.INTER_LINEAR)
        h = min(HAND_H, FRAME_SHAPE[0] - y)
        w = min(HAND_W, FRAME_SHAPE[1] - x)
        region = frame[y : y + h, x : x + w]
        painted = card[:h, :w]
        region[painted.any(axis=2)] = painted[painted.any(axis=2)]
        x += stride
    return frame


class HandZoneTests(unittest.TestCase):
    def setUp(self) -> None:
        self.reader = CardReader()

    def test_upright_hand_cards_are_read(self) -> None:
        rendered = ["5S", "9H"]
        cards = self.reader.detect(render_hand_frame(rendered))
        hand = [c.code for c in cards if c.zone is CardZone.MY_HAND]
        self.assertTrue(hand, "no hand card was read at all")
        # The contract is precision, not recall: the reader may refuse a card,
        # but it must never report one that is not there.
        self.assertEqual(set(hand) - set(rendered), set())

    def test_hand_cards_are_reported_in_the_hand_zone(self) -> None:
        cards = self.reader.detect(render_hand_frame(["5S"]))
        self.assertTrue(cards)
        self.assertTrue(all(c.zone is CardZone.MY_HAND for c in cards))

    def test_tilted_hand_card_is_never_misread(self) -> None:
        """A fan tilts each card. Deskewing may still refuse the read, but a
        tilted card must never come back as some other card."""
        for angle in (-8.0, -5.0, 0.0, 3.0):
            cards = self.reader.detect(render_hand_frame(["7D"], angle=angle))
            hand = [c.code for c in cards if c.zone is CardZone.MY_HAND]
            self.assertEqual(set(hand) - {"7D"}, set(), f"misread at {angle} deg")

    def test_tilted_hand_card_is_still_read(self) -> None:
        """The glyph window must not drift with the fan angle.

        Rotating about the white bounding box's top-left put the origin off the
        card, and the gap between the two moved with the angle, so a fixed window
        sampled a moving target and a tilted card was refused even when the same
        card upright was read. The origin is now re-derived after deskewing, so
        one card must survive the whole range a real fan spans.
        """
        for angle in (-8.0, -5.0, -3.0, 0.0, 2.0):
            cards = self.reader.detect(render_hand_frame(["5S"], angle=angle))
            hand = [c.code for c in cards if c.zone is CardZone.MY_HAND]
            self.assertEqual(hand, ["5S"], f"lost the card at {angle} deg")

    def test_deskew_recovers_the_rendered_angle(self) -> None:
        """The angle estimate is what makes the hand readable, so measure it.

        Only negative render angles are checked: this renderer rotates about the
        card's top-left corner, so a positive angle lifts the top edge out of the
        canvas and leaves a flat clipped edge behind. That is a limitation of the
        fixture, not of the estimator - real fans span -8.8 to +2.9 degrees.
        """
        for angle in (-8.0, -4.0, -1.0):
            frame = render_hand_frame(["7D"], angle=angle)
            white = self.reader._white_mask(frame)
            boxes, _labels = self.reader._hand_boxes(frame, white)
            self.assertTrue(boxes, f"no hand box at {angle} deg")
            measured = self.reader._top_edge_angle(white, boxes[0][0])
            self.assertIsNotNone(measured)
            # The renderer rotates about the origin with OpenCV's positive-is-
            # counter-clockwise convention; the reader reports the top edge's
            # slope, which runs the other way. Hence the negation.
            self.assertAlmostEqual(measured, -angle, delta=1.5)

    def test_hand_and_table_are_separated(self) -> None:
        frame = render_frame(["3S", "4C"])
        frame[500:, :] = render_hand_frame(["KC"])[500:, :]
        cards = self.reader.detect(frame)
        table = {c.code for c in cards if c.zone is CardZone.TABLE}
        self.assertEqual(table, {"3S", "4C"})
        for card in cards:
            if card.zone is CardZone.MY_HAND:
                self.assertEqual(card.code, "KC")

    def test_table_read_does_not_suppress_the_hand(self) -> None:
        """Detections are keyed on (code, zone), so the same code appearing in
        both zones must not collapse into one entry."""
        frame = render_frame(["9H"])
        frame[500:, :] = render_hand_frame(["9H"])[500:, :]
        codes = {(c.code, c.zone) for c in self.reader.detect(frame)}
        self.assertIn(("9H", CardZone.TABLE), codes)

    def test_hand_reading_is_disabled_without_templates(self) -> None:
        reader = CardReader(hand_template_path=None)
        cards = reader.detect(render_hand_frame(["5S", "9H"]))
        self.assertEqual([c for c in cards if c.zone is CardZone.MY_HAND], [])

    def test_hand_template_bank_is_complete(self) -> None:
        self.assertEqual(len(self.reader._hand_ranks), 13)
        self.assertEqual(set(self.reader._hand_suits), {"S", "C", "D", "H"})

    def test_hand_input_is_not_mutated(self) -> None:
        frame = render_hand_frame(["6S", "10C"])
        original = frame.copy()
        self.reader.detect(frame)
        np.testing.assert_array_equal(frame, original)


class SuitByShapeTests(unittest.TestCase):
    """The suit is decided by outline convexity, not by bitmap matching.

    Pips are drawn as polygons whose measured convexity matches what real pips
    produce (diamonds solidity 0.973-0.998 and 0 defects, hearts ~0.92 and 1,
    spades 0.874-0.973 and 0-2, clubs 0.811-0.893 and 3-4). The shipped
    templates cannot serve here: they are the mean of several samples, so
    re-rendering one yields a blurred blob rather than a faithful pip.
    """

    @staticmethod
    def _blank():
        return np.full((60, 60, 3), 255, dtype=np.uint8)

    def _diamond(self, colour=RED_INK):
        crop = self._blank()
        cv2.fillPoly(crop, [np.array([(30, 6), (52, 30), (30, 54), (8, 30)], np.int32)], colour)
        return crop

    def _heart(self, colour=RED_INK):
        crop = self._blank()
        cv2.circle(crop, (21, 24), 13, colour, -1)
        cv2.circle(crop, (39, 24), 13, colour, -1)
        cv2.fillPoly(crop, [np.array([(7, 28), (53, 28), (30, 54)], np.int32)], colour)
        return crop

    def _spade(self, colour=BLACK_INK):
        crop = self._blank()
        points = [(30, 8), (44, 30), (46, 38), (34, 40), (34, 46),
                  (26, 46), (26, 40), (14, 38), (16, 30)]
        cv2.fillPoly(crop, [np.array(points, np.int32)], colour)
        return crop

    def _club(self, colour=BLACK_INK):
        crop = self._blank()
        cv2.circle(crop, (30, 18), 11, colour, -1)
        cv2.circle(crop, (18, 34), 11, colour, -1)
        cv2.circle(crop, (42, 34), 11, colour, -1)
        cv2.rectangle(crop, (27, 34), (33, 54), colour, -1)
        return crop

    def test_diamond_is_convex_and_read_as_diamond(self) -> None:
        self.assertEqual(_suit_by_shape(self._diamond()), "D")

    def test_heart_is_distinguished_from_diamond(self) -> None:
        """Both are red, so only the notch between the lobes separates them."""
        self.assertEqual(_suit_by_shape(self._heart()), "H")

    def test_club_is_distinguished_from_spade(self) -> None:
        """Both are black; the club's three lobes give it extra hull defects."""
        self.assertEqual(_suit_by_shape(self._club()), "C")

    def test_spade_is_read_as_spade(self) -> None:
        self.assertEqual(_suit_by_shape(self._spade()), "S")

    def test_colour_gates_the_red_suits(self) -> None:
        """A diamond drawn in black must never be reported as a red suit."""
        self.assertNotIn(_suit_by_shape(self._diamond(colour=BLACK_INK)), {"D", "H"})

    def test_blank_crop_is_refused(self) -> None:
        self.assertIsNone(_suit_by_shape(self._blank()))

    def test_speck_too_small_is_refused(self) -> None:
        crop = self._blank()
        cv2.circle(crop, (30, 30), 2, BLACK_INK, -1)
        self.assertIsNone(_suit_by_shape(crop))


class SelectedCardTests(unittest.TestCase):
    """Tapping a hand card lifts it clear of the fan; that lift means selected."""

    def setUp(self) -> None:
        self.reader = CardReader()

    def test_a_card_lifted_above_its_neighbours_reads_as_selected(self) -> None:
        boxes = [((100, 540, 80, 200), 1), ((180, 460, 80, 220), 2), ((260, 535, 80, 200), 3)]
        self.assertEqual(self.reader._lifted(boxes), [False, True, False])

    def test_adjacent_lifted_cards_are_one_selected_plateau(self) -> None:
        boxes = [
            ((100, 540, 80, 180), 1),
            ((180, 460, 80, 220), 2),
            ((260, 464, 80, 220), 3),
            ((340, 535, 80, 185), 4),
        ]
        self.assertEqual(
            self.reader._lifted(boxes),
            [False, True, True, False],
        )

    def test_selected_plateau_at_the_edge_is_detected(self) -> None:
        boxes = [
            ((100, 460, 80, 220), 1),
            ((180, 463, 80, 220), 2),
            ((260, 535, 80, 185), 3),
            ((340, 530, 80, 190), 4),
        ]
        self.assertEqual(
            self.reader._lifted(boxes),
            [True, True, False, False],
        )

    def test_the_fans_own_curve_is_not_a_selection(self) -> None:
        """Adjacent cards in a real fan differ by at most 9px, well under the
        25px lift, so the whole arc must read as unselected."""
        tops = [540, 531, 524, 518, 514, 511, 510, 510, 510, 513, 517, 522, 530]
        boxes = [((100 + 70 * i, top, 80, 200), i + 1) for i, top in enumerate(tops)]
        self.assertEqual(self.reader._lifted(boxes), [False] * len(tops))

    def test_a_single_card_is_never_selected(self) -> None:
        self.assertEqual(self.reader._lifted([((100, 400, 80, 200), 1)]), [False])
