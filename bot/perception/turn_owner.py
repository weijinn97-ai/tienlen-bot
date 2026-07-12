from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

import numpy as np

from contracts.interfaces import Rect, SeatPosition, TurnOwnerEvidence, TurnPrimarySignal


@dataclass(frozen=True)
class NormalizedRect:
    """A resolution-independent ROI expressed as fractions of the frame."""

    x: float
    y: float
    width: float
    height: float

    def __post_init__(self) -> None:
        values = (self.x, self.y, self.width, self.height)
        if any(value < 0.0 or value > 1.0 for value in values):
            raise ValueError("NormalizedRect values must be within [0.0, 1.0].")
        if self.width == 0.0 or self.height == 0.0:
            raise ValueError("NormalizedRect width and height must be positive.")
        if self.x + self.width > 1.0 or self.y + self.height > 1.0:
            raise ValueError("NormalizedRect must fit inside the frame.")

    def to_rect(self, frame_width: int, frame_height: int) -> Rect:
        if frame_width <= 0 or frame_height <= 0:
            raise ValueError("Frame dimensions must be positive.")
        x = min(round(self.x * frame_width), frame_width - 1)
        y = min(round(self.y * frame_height), frame_height - 1)
        right = min(round((self.x + self.width) * frame_width), frame_width)
        bottom = min(round((self.y + self.height) * frame_height), frame_height)
        return Rect(x=x, y=y, width=max(1, right - x), height=max(1, bottom - y))


@dataclass(frozen=True)
class AvatarRoiLayout:
    rois: Mapping[SeatPosition, NormalizedRect]

    def __post_init__(self) -> None:
        missing = set(SeatPosition) - set(self.rois)
        if missing:
            names = ", ".join(seat.name for seat in sorted(missing, key=int))
            raise ValueError(f"Avatar ROI layout is missing seats: {names}.")

    def resolve(self, frame_width: int, frame_height: int) -> dict[SeatPosition, Rect]:
        return {
            seat: self.rois[seat].to_rect(frame_width, frame_height)
            for seat in SeatPosition
        }


# Calibrated from the repository's 1280x720 MEmu screenshot batch. Normalized
# coordinates preserve the same table layout at other 16:9 resolutions.
DEFAULT_AVATAR_LAYOUT = AvatarRoiLayout(
    rois={
        SeatPosition.SELF: NormalizedRect(0.008, 0.743, 0.098, 0.181),
        SeatPosition.LEFT: NormalizedRect(0.008, 0.250, 0.098, 0.181),
        SeatPosition.TOP: NormalizedRect(0.672, 0.007, 0.102, 0.181),
        SeatPosition.RIGHT: NormalizedRect(0.891, 0.250, 0.105, 0.181),
    }
)


@dataclass(frozen=True)
class HighlightDetection:
    owner: SeatPosition | None
    confidence: float
    roi: Rect | None
    scores: Mapping[SeatPosition, float]


class YellowHighlightDetector:
    """Detect the active avatar's gold timer ring using a small color mask."""

    def __init__(
        self,
        *,
        layout: AvatarRoiLayout = DEFAULT_AVATAR_LAYOUT,
        channel_order: str = "BGR",
        minimum_score: float = 0.055,
        minimum_margin: float = 0.012,
        ring_inner_radius: float = 0.72,
        ring_outer_radius: float = 1.04,
    ) -> None:
        normalized_order = channel_order.upper()
        if normalized_order not in {"BGR", "RGB"}:
            raise ValueError("channel_order must be BGR or RGB.")
        if not 0.0 <= minimum_score <= 1.0:
            raise ValueError("minimum_score must be within [0.0, 1.0].")
        if not 0.0 <= minimum_margin <= 1.0:
            raise ValueError("minimum_margin must be within [0.0, 1.0].")
        if ring_inner_radius < 0.0 or ring_outer_radius <= ring_inner_radius:
            raise ValueError("Ring radii are invalid.")
        self.layout = layout
        self.channel_order = normalized_order
        self.minimum_score = minimum_score
        self.minimum_margin = minimum_margin
        self.ring_inner_radius = ring_inner_radius
        self.ring_outer_radius = ring_outer_radius

    def detect(self, frame: np.ndarray) -> HighlightDetection:
        if not isinstance(frame, np.ndarray) or frame.ndim != 3 or frame.shape[2] < 3:
            raise ValueError("frame must be an HxWx3 numpy array.")
        frame_height, frame_width = frame.shape[:2]
        rois = self.layout.resolve(frame_width, frame_height)
        scores = {seat: self._gold_ring_score(frame, roi) for seat, roi in rois.items()}
        ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        best_seat, best_score = ranked[0]
        second_score = ranked[1][1]
        margin = best_score - second_score
        if best_score < self.minimum_score or margin < self.minimum_margin:
            return HighlightDetection(None, 0.0, None, scores)
        score_confidence = min(1.0, best_score / max(self.minimum_score * 2.0, 1e-9))
        margin_confidence = min(1.0, margin / max(self.minimum_margin * 3.0, 1e-9))
        confidence = round((score_confidence + margin_confidence) / 2.0, 6)
        return HighlightDetection(best_seat, confidence, rois[best_seat], scores)

    def _gold_ring_score(self, frame: np.ndarray, roi: Rect) -> float:
        crop = frame[roi.y : roi.y + roi.height, roi.x : roi.x + roi.width, :3]
        if crop.size == 0:
            return 0.0
        height, width = crop.shape[:2]
        radius_scale = min(width, height) / 2.0
        yy, xx = np.ogrid[:height, :width]
        normalized_radius = np.sqrt(
            ((xx - (width - 1) / 2.0) / radius_scale) ** 2
            + ((yy - (height - 1) / 2.0) / radius_scale) ** 2
        )
        ring_mask = (
            (normalized_radius >= self.ring_inner_radius)
            & (normalized_radius <= self.ring_outer_radius)
        )
        if self.channel_order == "BGR":
            blue, green, red = (crop[:, :, index] for index in range(3))
        else:
            red, green, blue = (crop[:, :, index] for index in range(3))
        red_i = red.astype(np.int16)
        green_i = green.astype(np.int16)
        gold_mask = (
            (red_i >= 160)
            & (green_i >= 105)
            & (blue <= 140)
            & ((red_i - green_i) <= 150)
        )
        return float(np.mean(gold_mask[ring_mask])) if np.any(ring_mask) else 0.0


@dataclass(frozen=True)
class CardCountDelta:
    actor: SeatPosition | None
    expected_next_owner: SeatPosition | None
    confidence: float
    changed_by: int = 0


@dataclass(frozen=True)
class TurnOwnerDetection:
    turn_owner: SeatPosition | None
    evidence: TurnOwnerEvidence | None
    primary: HighlightDetection
    secondary: CardCountDelta


class HybridTurnOwnerDetector:
    """Confirm turn ownership only when highlight and card-count delta agree."""

    def __init__(
        self,
        *,
        highlight_detector: YellowHighlightDetector | None = None,
        turn_order: Sequence[SeatPosition] = tuple(SeatPosition),
    ) -> None:
        normalized_order = tuple(turn_order)
        if len(normalized_order) != len(SeatPosition) or set(normalized_order) != set(SeatPosition):
            raise ValueError("turn_order must contain each seat exactly once.")
        self.highlight_detector = highlight_detector or YellowHighlightDetector()
        self.turn_order = normalized_order

    def detect(
        self,
        frame: np.ndarray,
        *,
        previous_card_counts: Mapping[SeatPosition, int],
        current_card_counts: Mapping[SeatPosition, int],
    ) -> TurnOwnerDetection:
        primary = self.highlight_detector.detect(frame)
        secondary = self.card_count_delta(previous_card_counts, current_card_counts)
        signals_agree = (
            primary.owner is not None
            and secondary.expected_next_owner is not None
            and primary.owner == secondary.expected_next_owner
        )
        evidence = None
        if primary.owner is not None and primary.roi is not None:
            notes = (
                f"primary={primary.owner.name};"
                f"actor={secondary.actor.name if secondary.actor is not None else 'unknown'};"
                f"expected_next={secondary.expected_next_owner.name if secondary.expected_next_owner is not None else 'unknown'}"
            )
            evidence = TurnOwnerEvidence(
                primary_signal=TurnPrimarySignal.AVATAR_HIGHLIGHT,
                primary_roi=primary.roi,
                primary_confidence=primary.confidence,
                secondary_confidence=secondary.confidence,
                signals_agree=signals_agree,
                notes=notes,
            )
        return TurnOwnerDetection(
            turn_owner=primary.owner if signals_agree else None,
            evidence=evidence,
            primary=primary,
            secondary=secondary,
        )

    def card_count_delta(
        self,
        previous: Mapping[SeatPosition, int],
        current: Mapping[SeatPosition, int],
    ) -> CardCountDelta:
        decreases: list[tuple[SeatPosition, int]] = []
        for seat in SeatPosition:
            before = previous.get(seat)
            after = current.get(seat)
            if before is None or after is None:
                continue
            if not 0 <= before <= 13 or not 0 <= after <= 13:
                raise ValueError("Card counts must be within [0, 13].")
            if after < before:
                decreases.append((seat, before - after))
        if len(decreases) != 1:
            return CardCountDelta(None, None, 0.0)
        actor, changed_by = decreases[0]
        actor_index = self.turn_order.index(actor)
        expected_next = self.turn_order[(actor_index + 1) % len(self.turn_order)]
        confidence = min(1.0, 0.75 + 0.05 * changed_by)
        return CardCountDelta(actor, expected_next, confidence, changed_by)
