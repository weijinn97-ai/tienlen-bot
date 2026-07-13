from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from bot.perception.turn_owner import NormalizedRect
from contracts.interfaces import ButtonId, ButtonState, Rect


@dataclass(frozen=True)
class ButtonTemplate:
    button_id: ButtonId
    label: str
    image: np.ndarray
    search_roi: NormalizedRect
    threshold: float = 0.82
    is_enabled: bool = True

    def __post_init__(self) -> None:
        if self.image.ndim not in {2, 3} or self.image.size == 0:
            raise ValueError("Button template image is invalid.")
        if not 0.0 < self.threshold <= 1.0:
            raise ValueError("Button template threshold must be within (0.0, 1.0].")


class TemplateButtonDetector:
    """Detect stable game buttons by template matching inside constrained ROIs."""

    def __init__(self, templates: tuple[ButtonTemplate, ...]) -> None:
        if not templates:
            raise ValueError("At least one button template is required.")
        self.templates = templates

    def detect(self, frame: np.ndarray) -> tuple[ButtonState, ...]:
        height, width = frame.shape[:2]
        detections: dict[ButtonId, ButtonState] = {}
        for template in self.templates:
            search = template.search_roi.to_rect(width, height)
            crop = frame[
                search.y : search.y + search.height,
                search.x : search.x + search.width,
            ]
            needle = template.image
            if needle.shape[0] > crop.shape[0] or needle.shape[1] > crop.shape[1]:
                continue
            match_crop, match_needle = self._matching_images(crop, needle)
            result = cv2.matchTemplate(match_crop, match_needle, cv2.TM_CCOEFF_NORMED)
            _, score, _, location = cv2.minMaxLoc(result)
            if score < template.threshold:
                continue
            x = search.x + location[0]
            y = search.y + location[1]
            observed = frame[y : y + needle.shape[0], x : x + needle.shape[1], :3]
            is_enabled = template.is_enabled
            if template.button_id == ButtonId.PLAY:
                is_enabled = self._green_enabled_ratio(observed) >= 0.15
            candidate = ButtonState(
                    button_id=template.button_id,
                    label=template.label,
                    roi=Rect(x, y, needle.shape[1], needle.shape[0]),
                    is_enabled=is_enabled,
                    confidence=float(score),
                )
            existing = detections.get(template.button_id)
            if existing is None or candidate.confidence > existing.confidence:
                detections[template.button_id] = candidate
        return tuple(detections.values())

    @staticmethod
    def _matching_images(crop: np.ndarray, needle: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        if crop.ndim == needle.ndim:
            return crop, needle
        if crop.ndim == 3:
            crop = cv2.cvtColor(crop[:, :, :3], cv2.COLOR_BGR2GRAY)
        if needle.ndim == 3:
            needle = cv2.cvtColor(needle[:, :, :3], cv2.COLOR_BGR2GRAY)
        return crop, needle

    @staticmethod
    def _green_enabled_ratio(image: np.ndarray) -> float:
        if image.ndim != 3:
            return 0.0
        blue, green, red = (image[:, :, index].astype(np.int16) for index in range(3))
        mask = (green > red + 20) & (green > blue + 20) & (green > 80)
        return float(np.mean(mask))


def load_gameplay_button_detector(template_dir: str | Path) -> TemplateButtonDetector:
    directory = Path(template_dir)
    search = NormalizedRect(0.25, 0.45, 0.5, 0.22)
    definitions = (
        ("pass_enabled.png", ButtonId.PASS, "Bỏ Lượt", True),
        ("play_enabled.png", ButtonId.PLAY, "Đánh", True),
        ("play_disabled.png", ButtonId.PLAY, "Đánh", False),
    )
    templates = []
    for filename, button_id, label, enabled in definitions:
        image = cv2.imread(str(directory / filename))
        if image is None:
            raise FileNotFoundError(directory / filename)
        templates.append(ButtonTemplate(button_id, label, image, search, 0.82, enabled))
    return TemplateButtonDetector(tuple(templates))
