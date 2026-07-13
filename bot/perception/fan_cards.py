from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from bot.agent.game_state_adapter import normalize_agent_card
from contracts.interfaces import CardZone, DetectedCard, Rect


@dataclass(frozen=True)
class FanGeometry:
    base_left: int = 137
    pitch: int = 70
    top: int = 505
    slot_width: int = 76
    feature_height: int = 145

    def rois(self, count: int) -> tuple[Rect, ...]:
        if count < 1 or count > 13:
            raise ValueError("Hand count must be within [1, 13].")
        left = self.base_left + (13 - count) * 35
        return tuple(
            Rect(
                left + index * self.pitch,
                self.top,
                110 if index == count - 1 else self.slot_width,
                self.feature_height,
            )
            for index in range(count)
        )


class FanCardTemplateRecognizer:
    """Fixed-layout fallback with independent rank and suit nearest templates."""

    def __init__(
        self,
        rank_features: np.ndarray,
        rank_labels: tuple[str, ...],
        suit_features: np.ndarray,
        suit_labels: tuple[str, ...],
        *,
        geometry: FanGeometry = FanGeometry(),
    ) -> None:
        if not rank_labels or len(rank_features) != len(rank_labels):
            raise ValueError("Rank templates are empty or misaligned.")
        if not suit_labels or len(suit_features) != len(suit_labels):
            raise ValueError("Suit templates are empty or misaligned.")
        self.rank_features = rank_features.astype(np.float32)
        self.rank_labels = rank_labels
        self.suit_features = suit_features.astype(np.float32)
        self.suit_labels = suit_labels
        self.geometry = geometry

    @classmethod
    def from_submission_batch(
        cls,
        batch_dir: str | Path,
        *,
        geometry: FanGeometry = FanGeometry(),
    ) -> "FanCardTemplateRecognizer":
        directory = Path(batch_dir)
        rank_features, rank_labels = [], []
        suit_features, suit_labels = [], []
        with (directory / "manifest.csv").open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                cards = [normalize_agent_card(card) for card in row["cards_visible"].split(";") if card]
                if len(cards) != 13:
                    continue
                frame = cv2.imread(str(directory / "raw" / row["source_filename"]))
                if frame is None:
                    continue
                for card, roi in zip(cards, geometry.rois(13)):
                    rank, suit = card[:-1], card[-1]
                    rank_feature, suit_feature = cls._features(frame, roi)
                    rank_features.append(rank_feature)
                    rank_labels.append(rank)
                    suit_features.append(suit_feature)
                    suit_labels.append(suit)
        return cls(
            np.stack(rank_features),
            tuple(rank_labels),
            np.stack(suit_features),
            tuple(suit_labels),
            geometry=geometry,
        )

    def detect(self, frame: np.ndarray, hand_count: int) -> tuple[DetectedCard, ...]:
        detections = []
        for roi in self.geometry.rois(hand_count):
            rank_feature, suit_feature = self._features(frame, roi)
            rank, rank_confidence = self._nearest(
                rank_feature, self.rank_features, self.rank_labels
            )
            suit, suit_confidence = self._nearest_suit(suit_feature)
            detections.append(
                DetectedCard(
                    f"{rank}{suit}",
                    roi,
                    CardZone.MY_HAND,
                    min(rank_confidence, suit_confidence),
                )
            )
        return tuple(detections)

    @staticmethod
    def _nearest(
        feature: np.ndarray,
        templates: np.ndarray,
        labels: tuple[str, ...],
    ) -> tuple[str, float]:
        distances = np.mean((templates - feature) ** 2, axis=1)
        ranked = np.argsort(distances)
        best_index = int(ranked[0])
        best = float(distances[best_index])
        second = next(
            (float(distances[index]) for index in ranked[1:] if labels[index] != labels[best_index]),
            best,
        )
        confidence = min(1.0, max(0.0, second - best) / 0.01)
        return labels[best_index], confidence

    def _nearest_suit(self, feature: np.ndarray) -> tuple[str, float]:
        is_red = float(feature[-1]) >= 0.05
        allowed = {"D", "H"} if is_red else {"S", "C"}
        indices = [index for index, label in enumerate(self.suit_labels) if label in allowed]
        templates = self.suit_features[indices]
        labels = tuple(self.suit_labels[index] for index in indices)
        return self._nearest(feature, templates, labels)

    @staticmethod
    def _features(frame: np.ndarray, roi: Rect) -> tuple[np.ndarray, np.ndarray]:
        crop = frame[roi.y : roi.y + roi.height, roi.x : roi.x + roi.width, :3]
        rank_crop = crop[12:78, 12:min(90, crop.shape[1])]
        return (
            FanCardTemplateRecognizer._normalize(rank_crop, (28, 36)),
            FanCardTemplateRecognizer._suit_shape(crop),
        )

    @staticmethod
    def _normalize(image: np.ndarray, size: tuple[int, int]) -> np.ndarray:
        resized = cv2.resize(image, size, interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
        return resized.reshape(-1)

    @staticmethod
    def _suit_shape(card_crop: np.ndarray) -> np.ndarray:
        region = card_crop[58:145, 8:min(68, card_crop.shape[1])]
        gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
        mask = cv2.threshold(gray, 185, 255, cv2.THRESH_BINARY_INV)[1]
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        candidates = [contour for contour in contours if cv2.contourArea(contour) >= 30]
        if not candidates:
            return np.zeros(32 * 32 + 16, dtype=np.float32)
        contour = max(candidates, key=cv2.contourArea)
        x, y, width, height = cv2.boundingRect(contour)
        symbol = mask[y : y + height, x : x + width]
        normalized = cv2.resize(symbol, (32, 32), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
        blue, green, red = (region[:, :, index].astype(np.float32) for index in range(3))
        red_dominance = float(np.mean((red > green + 25) & (red > blue + 25)))
        color_feature = np.full(16, red_dominance, dtype=np.float32)
        return np.concatenate((normalized.reshape(-1), color_feature))
