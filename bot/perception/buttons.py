from __future__ import annotations

from dataclasses import dataclass

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
        detections = []
        for template in self.templates:
            search = template.search_roi.to_rect(width, height)
            crop = frame[
                search.y : search.y + search.height,
                search.x : search.x + search.width,
            ]
            needle = template.image
            if needle.shape[0] > crop.shape[0] or needle.shape[1] > crop.shape[1]:
                continue
            crop_gray = self._gray(crop)
            needle_gray = self._gray(needle)
            result = cv2.matchTemplate(crop_gray, needle_gray, cv2.TM_CCOEFF_NORMED)
            _, score, _, location = cv2.minMaxLoc(result)
            if score < template.threshold:
                continue
            x = search.x + location[0]
            y = search.y + location[1]
            detections.append(
                ButtonState(
                    button_id=template.button_id,
                    label=template.label,
                    roi=Rect(x, y, needle.shape[1], needle.shape[0]),
                    confidence=float(score),
                )
            )
        return tuple(detections)

    @staticmethod
    def _gray(image: np.ndarray) -> np.ndarray:
        return image if image.ndim == 2 else cv2.cvtColor(image[:, :, :3], cv2.COLOR_BGR2GRAY)
