"""Template-matching card reader for the fixed-sprite table renderer.

The game draws cards as fixed sprites at a fixed scale, so a card's corner index
is the same pixels every time it appears. That makes classical template matching
a better fit than a learned detector: it needs no training data, no annotation
and no GPU, and it runs in single-digit milliseconds.

Scope: `CardZone.TABLE` only. Hand cards are drawn larger and rotated into a fan,
and the flat templates do not transfer to them - measured duplicate rate is 30.9%
in the hand zone against 3.0% on the table. Reading the hand needs deskewing and
its own template bank; until that exists this reader must not be pointed at it.

Precision is preferred over recall throughout. A dropped card is retried by the
next frame; a wrong card produces an illegal play that nothing downstream can
recover from.
"""
from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import cv2
import numpy as np

from contracts.interfaces import CardZone, DetectedCard, Rect

TEMPLATE_ASSET = Path(__file__).resolve().parent / "card_templates.npz"

FRAME_SHAPE = (720, 1280, 3)
WHITE_THRESHOLD = 190
INK_THRESHOLD = 160
GLYPH_SIZE = (24, 32)  # (w, h)

# Card box filter for the table zone, measured from real 1280x720 frames.
TABLE_HEIGHT = (110, 145)
MIN_CARD_WIDTH = 28

# Glyph windows as a fraction of card height.
RANK_Y = (0.03, 0.33)
SUIT_Y = (0.34, 0.56)
GLYPH_X = (0.02, 0.42)

# A rank further than this from all 13 templates is refused rather than guessed.
# At 0.20 the labelled set reads with no errors; 0.25 admits three, so the extra
# recall is not worth it.
MAX_RANK_DISTANCE = 0.20

# Suits are judged on margin, not absolute distance. Colour has already reduced
# the field to two candidates, so the question is only "which of these two", and
# suit glyphs vary more than rank glyphs (mean intra-class spread 0.156 for
# hearts against ~0.09 elsewhere). An absolute cut at rank strictness would throw
# away correct reads whose rank matched exactly.
# Swept against the labelled set: 0.010-0.025 all hold precision at 100% with
# recall 80.4%; 0.0 drops to 95.3% precision, and 0.04 costs 12 points of recall
# for nothing. 0.015 sits in the middle of the safe plateau.
MIN_SUIT_MARGIN = 0.015
MAX_SUIT_DISTANCE = 0.32

RED_SUITS = frozenset({"D", "H"})
MIN_RED_DOMINANCE = 25.0
MIN_INK_PIXELS = 25


class CardReaderError(RuntimeError):
    """Raised when the template asset is missing or malformed."""


def _load_templates(path: Path) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    if not path.is_file():
        raise CardReaderError(f"Card template asset not found: {path}")
    with np.load(path, allow_pickle=False) as data:
        ranks = {
            str(k): data["rank"][i].astype(np.float32) / 255.0
            for i, k in enumerate(data["rank_keys"])
        }
        suits = {
            str(k): data["suit"][i].astype(np.float32) / 255.0
            for i, k in enumerate(data["suit_keys"])
        }
    if len(ranks) != 13 or len(suits) != 4:
        raise CardReaderError(
            f"Template asset must hold 13 ranks and 4 suits, got {len(ranks)} and {len(suits)}."
        )
    return ranks, suits


def _normalise_glyph(crop: np.ndarray) -> np.ndarray | None:
    """Binarise, crop to the ink bounding box, and resize to the template size."""
    grey = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    _, ink = cv2.threshold(grey, INK_THRESHOLD, 255, cv2.THRESH_BINARY_INV)
    ys, xs = np.nonzero(ink)
    if len(xs) < MIN_INK_PIXELS:
        return None
    tight = ink[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]
    resized = cv2.resize(tight, GLYPH_SIZE, interpolation=cv2.INTER_AREA)
    return resized.astype(np.float32) / 255.0


def _is_red(crop: np.ndarray) -> bool:
    blue, green, red = (crop[:, :, i].astype(np.int16) for i in range(3))
    ink = (blue + green + red) < 520
    if int(ink.sum()) < 20:
        return False
    dominance = (red[ink] - np.maximum(green[ink], blue[ink])).mean()
    return float(dominance) > MIN_RED_DOMINANCE


class CardReader:
    """Reads table cards from a frame. Stateless and safe to share."""

    def __init__(self, template_path: Path | str = TEMPLATE_ASSET) -> None:
        self._ranks, self._suits = _load_templates(Path(template_path))

    # The template bank is loaded in __init__ and there is no lazy state, so
    # the first detect() costs the same as every later one. Callers still get an
    # explicit warm-up hook because the pipeline contract requires one.
    def warm_up(self) -> None:
        """No-op: this reader has no deferred initialisation."""

    def detect(self, image: np.ndarray) -> Sequence[DetectedCard]:
        if not isinstance(image, np.ndarray):
            raise ValueError("Card reader expects a numpy array.")
        if image.shape != FRAME_SHAPE:
            raise ValueError(f"Card reader expects {FRAME_SHAPE} frames, got {image.shape}.")

        detections: dict[str, DetectedCard] = {}
        for box in self._card_boxes(image):
            result = self._classify(image, box)
            if result is None:
                continue
            code, confidence = result
            x, y, width, height = box
            existing = detections.get(code)
            if existing is not None:
                # The same physical card cannot appear twice. Keep the stronger
                # read and drop the other rather than emitting a known error.
                if existing.confidence >= confidence:
                    continue
            detections[code] = DetectedCard(
                code=code,
                roi=Rect(x=x, y=y, width=width, height=height),
                zone=CardZone.TABLE,
                confidence=confidence,
            )

        return tuple(
            sorted(detections.values(), key=lambda c: (c.roi.y, c.roi.x, c.code))
        )

    def _card_boxes(self, image: np.ndarray) -> list[tuple[int, int, int, int]]:
        grey = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        _, mask = cv2.threshold(grey, WHITE_THRESHOLD, 255, cv2.THRESH_BINARY)
        count, _, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
        boxes = []
        for index in range(1, count):
            x = int(stats[index, cv2.CC_STAT_LEFT])
            y = int(stats[index, cv2.CC_STAT_TOP])
            width = int(stats[index, cv2.CC_STAT_WIDTH])
            height = int(stats[index, cv2.CC_STAT_HEIGHT])
            if width >= MIN_CARD_WIDTH and TABLE_HEIGHT[0] <= height <= TABLE_HEIGHT[1]:
                boxes.append((x, y, width, height))
        return boxes

    def _window(
        self, image: np.ndarray, box: tuple[int, int, int, int], y_fraction: tuple[float, float]
    ) -> np.ndarray | None:
        x, y, width, height = box
        y0 = y + int(height * y_fraction[0])
        y1 = y + int(height * y_fraction[1])
        x0 = x + int(height * GLYPH_X[0])
        x1 = x + min(width, int(height * GLYPH_X[1]))
        if x1 - x0 < 8 or y1 - y0 < 8:
            return None
        crop = image[y0:y1, x0:x1]
        return crop if crop.size else None

    def _classify(
        self, image: np.ndarray, box: tuple[int, int, int, int]
    ) -> tuple[str, float] | None:
        rank_crop = self._window(image, box, RANK_Y)
        suit_crop = self._window(image, box, SUIT_Y)
        if rank_crop is None or suit_crop is None:
            return None
        rank_glyph = _normalise_glyph(rank_crop)
        suit_glyph = _normalise_glyph(suit_crop)
        if rank_glyph is None or suit_glyph is None:
            return None

        rank, rank_distance, runner_up = self._match(self._ranks, rank_glyph)
        if rank is None or rank_distance > MAX_RANK_DISTANCE:
            return None

        # Colour narrows the suit to two candidates before shape matching, which
        # removes the whole class of red/black confusions.
        red = _is_red(suit_crop)
        candidates = {k: v for k, v in self._suits.items() if (k in RED_SUITS) == red}
        suit, suit_distance, suit_runner_up = self._match(candidates, suit_glyph)
        if suit is None or suit_distance > MAX_SUIT_DISTANCE:
            return None
        if suit_runner_up - suit_distance < MIN_SUIT_MARGIN:
            return None

        margin = max(0.0, runner_up - rank_distance)
        quality = max(0.0, 1.0 - (rank_distance + suit_distance))
        confidence = min(1.0, quality * (0.5 + min(1.0, margin * 8.0)))
        return f"{rank}{suit}", float(confidence)

    @staticmethod
    def _match(
        templates: dict[str, np.ndarray], glyph: np.ndarray
    ) -> tuple[str | None, float, float]:
        best_key, best = None, float("inf")
        runner_up = float("inf")
        for key, template in templates.items():
            distance = float(np.abs(template - glyph).mean())
            if distance < best:
                best_key, runner_up, best = key, best, distance
            elif distance < runner_up:
                runner_up = distance
        return best_key, best, runner_up
