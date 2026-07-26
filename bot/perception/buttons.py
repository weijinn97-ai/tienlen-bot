from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from bot.perception.turn_owner import NormalizedRect
from contracts.interfaces import ButtonId, ButtonState, Rect

# Templates smaller than this are matched at full resolution.
MIN_SUBSAMPLED_TEMPLATE = 40


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
            step = self._match_step(needle)
            match_crop, match_needle = self._matching_images(
                crop[::step, ::step], needle[::step, ::step]
            )
            result = cv2.matchTemplate(match_crop, match_needle, cv2.TM_CCOEFF_NORMED)
            _, score, _, location = cv2.minMaxLoc(result)
            if score < template.threshold:
                continue
            x = search.x + location[0] * step
            y = search.y + location[1] * step
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
    def _match_step(needle: np.ndarray) -> int:
        """Correlate every other pixel when the template is big enough to spare it.

        Correlation cost is quadratic in scale, so sampling every second row and
        column does a quarter of the work. The gameplay buttons are around
        200x70, and on 590 recorded frames the halved match reached exactly the
        same decision on every one, with the reported centre never more than a
        pixel from the full-resolution answer - against 34ms down to 8ms, four
        times the card reader's cost removed from every look at the screen.

        Small templates are matched whole: there is nothing to save and the
        margin for error is thinner.
        """
        return 2 if min(needle.shape[:2]) >= MIN_SUBSAMPLED_TEMPLATE else 1

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
    # "Hủy tự động" does not sit in the action band: it is drawn over the fan,
    # low and centred, so it needs its own search window.
    cancel_search = NormalizedRect(0.31, 0.75, 0.40, 0.23)
    # "Tiếp Tục" appears on the round-end screen, right of centre, and is what
    # keeps a session going from one round to the next.
    continue_search = NormalizedRect(0.50, 0.52, 0.30, 0.20)
    definitions = (
        ("pass_enabled.png", ButtonId.PASS, "Bỏ Lượt", True, search),
        ("play_enabled.png", ButtonId.PLAY, "Đánh", True, search),
        ("play_disabled.png", ButtonId.PLAY, "Đánh", False, search),
        ("cancel_auto.png", ButtonId.CANCEL_AUTO, "Hủy tự động", True, cancel_search),
        ("continue_round.png", ButtonId.READY, "Tiếp Tục", True, continue_search),
    )
    templates = []
    for filename, button_id, label, enabled, roi in definitions:
        image = cv2.imread(str(directory / filename))
        if image is None:
            raise FileNotFoundError(directory / filename)
        templates.append(ButtonTemplate(button_id, label, image, roi, 0.82, enabled))
    return TemplateButtonDetector(tuple(templates))
