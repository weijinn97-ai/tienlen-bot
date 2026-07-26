"""Template-matching card reader for the fixed-sprite table renderer.

The game draws cards as fixed sprites at a fixed scale, so a card's corner index
is the same pixels every time it appears. That makes classical template matching
a better fit than a learned detector: it needs no training data, no annotation
and no GPU, and it runs in single-digit milliseconds.

Both zones are supported, but they need different handling. Table cards are drawn
flat and axis-aligned. Hand cards are drawn about 1.6x larger and rotated into a
fan (measured -8.8 to +2.9 degrees across a 13-card hand), and are clipped by the
bottom of the screen, so their bounding box height is not the card height. Each
hand card is therefore deskewed by the angle of its own top edge before its index
is read, and matched against a separate template bank: reusing the flat table
templates on hand glyphs scores 0/13.

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
HAND_TEMPLATE_ASSET = Path(__file__).resolve().parent / "hand_templates.npz"

FRAME_SHAPE = (720, 1280, 3)
WHITE_THRESHOLD = 190
INK_THRESHOLD = 160
GLYPH_SIZE = (24, 32)  # (w, h)

# Card box filters, measured from real 1280x720 frames.
TABLE_HEIGHT = (110, 145)
HAND_HEIGHT = (170, 225)
HAND_MIN_Y = 450
MIN_CARD_WIDTH = 28

# Tapping a hand card lifts it clear of the fan. Measured live: the lifted card
# sat at y=460 between neighbours at 516 and 510, so the gap is about 50px while
# the fan's own curve moves at most 9px between adjacent cards. 25px separates
# the two without being tight.
SELECTED_LIFT = 25

# Table glyph windows as a fraction of card height.
RANK_Y = (0.03, 0.33)
SUIT_Y = (0.34, 0.56)
GLYPH_X = (0.02, 0.42)

# Hand cards render about 1.62x table size. Their box height is set by screen
# clipping rather than by the card, so these windows are absolute pixel offsets
# from the deskewed card's top-left corner instead of fractions of the box.
# Measured over 1329 hand cells against the corrected origin: the rank glyph
# spans x 14-61, y 7-76 (sd 1.8 top, 1.2 bottom) and the pip x 17-58, y 77-117.
# The windows sit just outside that, and the boundary at 77 keeps the pip out of
# the rank window and the digits out of the pip window.
HAND_SCALE = 1.62
HAND_RANK_BOX = (12, 5, 63, 77)
HAND_SUIT_BOX = (15, 77, 60, 119)
HAND_EDGE_SAMPLE = 60
MIN_EDGE_POINTS = 10

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

# Hand ranks are cut tighter than table ranks. Deskewing leaves residual blur, so
# a loose gate lets warped glyphs through: at 0.20 the labelled accuracy is
# unchanged but 9.5% of hands come back out of sort order, which is proof of
# error. 0.17 holds precision and recall exactly while dropping that to 0.5%, and
# tightening further only costs cards without fixing the last violation.
MAX_HAND_RANK_DISTANCE = 0.17

RED_SUITS = frozenset({"D", "H"})
MIN_RED_DOMINANCE = 25.0
MIN_INK_PIXELS = 25

# Suit-by-outline thresholds. Measured on the labelled hand set: diamonds sit at
# solidity 0.973-0.998, hearts 0.905-0.936, spades 0.874-0.973, clubs 0.811-0.893.
MIN_SUIT_AREA = 50.0
MIN_DEFECT_DEPTH = 3.0
CLUB_MIN_DEFECTS = 3
SOLIDITY_DIAMOND = 0.955
SOLIDITY_CLUB_MAX = 0.860


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


def _suit_by_shape(crop: np.ndarray) -> str | None:
    """Identify a suit from its outline rather than by template matching.

    The four pips differ in convexity, and that is a far stronger signal than
    the normalised bitmap: matching the bitmap confuses hearts with diamonds and
    clubs with spades, scoring 81.1% on the labelled hand set, because resizing a
    near-square pip into the rank glyph box washes the shapes together.

    Counting convex-hull defects instead separates them far better - a club has
    three lobes, a diamond is convex, a heart has one notch, a spade has a stem.
    Colour has already split red from black, so only D-vs-H and S-vs-C remain.

    Those two questions are not equally settled. Red is clean: on 156 labelled
    pips diamonds sit at 0 defects 78/78 and hearts never crossed over, so the
    split is exact. Black is not. An independent check on the same 156 samples
    found 3 of 79 spades reaching 3 defects and 11 of 77 clubs falling below it,
    so the classes overlap and no threshold closes the gap - the ceiling for any
    single one of solidity, defect count or defect depth is about 95.5%. The
    shipped rule scores 95.9% on black pips it does not refuse. Separating them
    reliably needs a second feature, not a re-tuned constant.

    Solidity is kept as a guard so an unexpected shape is refused rather than
    forced into the nearest class.
    """
    grey = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    _, ink = cv2.threshold(grey, INK_THRESHOLD, 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(ink, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    contour = max(contours, key=cv2.contourArea)
    area = cv2.contourArea(contour)
    if area < MIN_SUIT_AREA:
        return None
    hull_area = cv2.contourArea(cv2.convexHull(contour))
    if hull_area <= 0:
        return None
    solidity = area / hull_area

    try:
        defects = cv2.convexityDefects(contour, cv2.convexHull(contour, returnPoints=False))
    except cv2.error:
        return None
    if defects is None:
        depth = 0
    else:
        # OpenCV returns (N, 1, 4) on some builds and (N, 4) on others, so
        # reshape rather than index a fixed rank. Column 3 is the defect depth
        # in fixed-point 8.8 format, hence the 256.
        rows = np.asarray(defects).reshape(-1, 4)
        depth = int((rows[:, 3] / 256.0 > MIN_DEFECT_DEPTH).sum())

    if _is_red(crop):
        if depth == 0 and solidity > SOLIDITY_DIAMOND:
            return "D"
        if depth == 1 and solidity < SOLIDITY_DIAMOND:
            return "H"
        return None
    if depth >= CLUB_MIN_DEFECTS:
        return "C"
    if depth <= 2 and solidity > SOLIDITY_CLUB_MAX:
        return "S"
    return None


def _is_red(crop: np.ndarray) -> bool:
    blue, green, red = (crop[:, :, i].astype(np.int16) for i in range(3))
    ink = (blue + green + red) < 520
    if int(ink.sum()) < 20:
        return False
    dominance = (red[ink] - np.maximum(green[ink], blue[ink])).mean()
    return float(dominance) > MIN_RED_DOMINANCE


class CardReader:
    """Reads table and hand cards from a frame. Stateless and safe to share."""

    def __init__(
        self,
        template_path: Path | str = TEMPLATE_ASSET,
        hand_template_path: Path | str | None = HAND_TEMPLATE_ASSET,
    ) -> None:
        self._ranks, self._suits = _load_templates(Path(template_path))
        self._hand_ranks: dict[str, np.ndarray] | None = None
        self._hand_suits: dict[str, np.ndarray] | None = None
        if hand_template_path is not None:
            self._hand_ranks, self._hand_suits = _load_templates(Path(hand_template_path))

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

        white = self._white_mask(image)
        detections: dict[tuple[str, CardZone], DetectedCard] = {}

        for box in self._card_boxes(image):
            self._collect(detections, image, box, CardZone.TABLE, self._classify(image, box))

        if self._hand_ranks is not None:
            boxes, labels = self._hand_boxes(image, white)
            lifted = self._lifted(boxes)
            for position, (box, index) in enumerate(boxes):
                self._collect(
                    detections, image, box,
                    CardZone.SELECTED if lifted[position] else CardZone.MY_HAND,
                    self._classify_hand(image, box, white, labels, index),
                )

        return tuple(
            sorted(detections.values(), key=lambda c: (c.zone.value, c.roi.y, c.roi.x, c.code))
        )

    @staticmethod
    def _collect(detections, image, box, zone, result) -> None:
        if result is None:
            return
        code, confidence = result
        x, y, width, height = box
        key = (code, zone)
        existing = detections.get(key)
        # The same physical card cannot appear twice in one zone. Keep the
        # stronger read and drop the other rather than emitting a known error.
        if existing is not None and existing.confidence >= confidence:
            return
        detections[key] = DetectedCard(
            code=code,
            roi=Rect(x=x, y=y, width=width, height=height),
            zone=zone,
            confidence=confidence,
        )

    @staticmethod
    def _white_mask(image: np.ndarray) -> np.ndarray:
        grey = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        _, mask = cv2.threshold(grey, WHITE_THRESHOLD, 255, cv2.THRESH_BINARY)
        return mask

    def _hand_boxes(
        self, image: np.ndarray, white: np.ndarray
    ) -> tuple[list[tuple[tuple[int, int, int, int], int]], np.ndarray]:
        """Return each hand cell with its component label, plus the label image.

        The label travels with the box because deskewing later needs this card's
        pixels alone, and a cropped patch can split a component so that its
        bounding box no longer identifies it.
        """
        count, labels, stats, _ = cv2.connectedComponentsWithStats(white, 8)
        boxes = []
        for index in range(1, count):
            x = int(stats[index, cv2.CC_STAT_LEFT])
            y = int(stats[index, cv2.CC_STAT_TOP])
            width = int(stats[index, cv2.CC_STAT_WIDTH])
            height = int(stats[index, cv2.CC_STAT_HEIGHT])
            if (
                width >= MIN_CARD_WIDTH
                and HAND_HEIGHT[0] <= height <= HAND_HEIGHT[1]
                and y > HAND_MIN_Y
            ):
                boxes.append(((x, y, width, height), index))
        return sorted(boxes), labels

    @staticmethod
    def _top_edge_angle(white: np.ndarray, box: tuple[int, int, int, int]) -> float | None:
        """Fit the card's visible top edge; its slope is the fan rotation."""
        x, y, width, _height = box
        xs, ys = [], []
        for column in range(x + 3, x + min(width, HAND_EDGE_SAMPLE)):
            rows = np.nonzero(white[y : y + HAND_EDGE_SAMPLE, column])[0]
            if len(rows):
                xs.append(column)
                ys.append(y + int(rows[0]))
        if len(xs) < MIN_EDGE_POINTS:
            return None
        slope = float(np.polyfit(np.array(xs, dtype=float), np.array(ys, dtype=float), 1)[0])
        return float(np.degrees(np.arctan(slope)))

    def _classify_hand(
        self,
        image: np.ndarray,
        box: tuple[int, int, int, int],
        white: np.ndarray,
        labels: np.ndarray,
        index: int,
    ) -> tuple[str, float] | None:
        angle = self._top_edge_angle(white, box)
        if angle is None:
            return None
        x, y, width, _height = box
        pad = 40
        x0, y0 = max(0, x - pad), max(0, y - pad)
        x1 = min(image.shape[1], x + min(width, 120) + pad)
        y1 = min(image.shape[0], y + 140 + pad)
        patch = image[y0:y1, x0:x1]
        if patch.size == 0:
            return None
        centre = (float(x - x0), float(y - y0))
        matrix = cv2.getRotationMatrix2D(centre, angle, 1.0)
        size = (patch.shape[1], patch.shape[0])
        upright = cv2.warpAffine(
            patch, matrix, size,
            flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE,
        )
        origin = self._upright_origin(labels[y0:y1, x0:x1], index, matrix, size)
        if origin is None:
            return None
        cx, cy = origin
        crops = []
        for bx0, by0, bx1, by1 in (HAND_RANK_BOX, HAND_SUIT_BOX):
            crop = upright[cy + by0 : cy + by1, cx + bx0 : cx + bx1]
            if crop.size == 0:
                return None
            crops.append(crop)
        return self._decide_hand(crops[0], crops[1])

    @staticmethod
    def _lifted(boxes: list[tuple[tuple[int, int, int, int], int]]) -> list[bool]:
        """Flag hand cells the player has already selected.

        A tapped card rises clear of the fan. The fan itself is a smooth curve -
        adjacent cards differ by at most 9px in the observed hands - so a card
        sitting well above both its neighbours is selected, not just further
        along the arc. Comparing against neighbours rather than an absolute row
        keeps this true wherever the fan sits on screen.

        Without this the bot re-taps a card it has already selected, which
        deselects it, and the turn loops until the clock runs out.
        """
        tops = [box[1] for box, _index in boxes]
        flags = []
        for position, top in enumerate(tops):
            neighbours = tops[max(0, position - 1) : position] + tops[position + 1 : position + 2]
            if not neighbours:
                flags.append(False)
                continue
            flags.append(top + SELECTED_LIFT < min(neighbours))
        return flags

    @staticmethod
    def _upright_origin(
        label_patch: np.ndarray,
        index: int,
        matrix: np.ndarray,
        size: tuple[int, int],
    ) -> tuple[int, int] | None:
        """Locate the card's own top-left corner after the patch is deskewed.

        Rotating about the bounding box's top-left is convenient but wrong: for a
        tilted card that point is not on the card at all, and the gap between the
        two moves with the fan angle (measured over 2058 hand cells, the offset
        correlates +0.86 in x and -0.96 in y with the angle). A fixed glyph window
        anchored there samples a moving target. Once the card is upright its own
        component's bounding box starts at its corner, so re-deriving the origin
        after the rotation removes the angle dependence without a fitted constant.
        """
        own = cv2.warpAffine(
            ((label_patch == index) * 255).astype(np.uint8), matrix, size,
            flags=cv2.INTER_NEAREST, borderMode=cv2.BORDER_CONSTANT, borderValue=0,
        )
        ys, xs = np.nonzero(own)
        if len(xs) == 0:
            return None
        return int(xs.min()), int(ys.min())

    def _decide_hand(self, rank_crop, suit_crop) -> tuple[str, float] | None:
        rank_glyph = _normalise_glyph(rank_crop)
        if rank_glyph is None:
            return None
        rank, rank_distance, runner_up = self._match(self._hand_ranks, rank_glyph)
        if rank is None or rank_distance > MAX_HAND_RANK_DISTANCE:
            return None
        suit = _suit_by_shape(suit_crop)
        if suit is None:
            return None
        margin = max(0.0, runner_up - rank_distance)
        quality = max(0.0, 1.0 - rank_distance)
        confidence = min(1.0, quality * (0.5 + min(1.0, margin * 8.0)))
        return f"{rank}{suit}", float(confidence)

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
        return self._decide(rank_crop, suit_crop, self._ranks, self._suits)

    def _decide(
        self,
        rank_crop: np.ndarray,
        suit_crop: np.ndarray,
        rank_templates: dict[str, np.ndarray],
        suit_templates: dict[str, np.ndarray],
        *,
        suit_margin: float = MIN_SUIT_MARGIN,
    ) -> tuple[str, float] | None:
        rank_glyph = _normalise_glyph(rank_crop)
        suit_glyph = _normalise_glyph(suit_crop)
        if rank_glyph is None or suit_glyph is None:
            return None

        rank, rank_distance, runner_up = self._match(rank_templates, rank_glyph)
        if rank is None or rank_distance > MAX_RANK_DISTANCE:
            return None

        # Colour narrows the suit to two candidates before shape matching, which
        # removes the whole class of red/black confusions.
        red = _is_red(suit_crop)
        candidates = {k: v for k, v in suit_templates.items() if (k in RED_SUITS) == red}
        suit, suit_distance, suit_runner_up = self._match(candidates, suit_glyph)
        if suit is None or suit_distance > MAX_SUIT_DISTANCE:
            return None
        if suit_runner_up - suit_distance < suit_margin:
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
