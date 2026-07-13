from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Mapping

import numpy as np

from bot.agent.game_state_adapter import normalize_agent_card
from contracts.interfaces import CardZone, DetectedCard, Rect


class YoloCardConfigurationError(RuntimeError):
    pass


class YoloCardDetector:
    """Ultralytics adapter that refuses weights without the exact 52-card taxonomy."""

    def __init__(
        self,
        weights_path: str | Path,
        *,
        confidence: float = 0.65,
        model_factory: Callable[[str], Any] | None = None,
    ) -> None:
        if not 0.0 < confidence <= 1.0:
            raise ValueError("confidence must be within (0.0, 1.0].")
        weights = Path(weights_path)
        if model_factory is None and not weights.is_file():
            raise YoloCardConfigurationError(f"YOLO weights not found: {weights}")
        if model_factory is None:
            try:
                from ultralytics import YOLO
            except ImportError as exc:
                raise YoloCardConfigurationError(
                    "Install 'ultralytics' before enabling YOLO card perception."
                ) from exc
            model_factory = YOLO
        self.model = model_factory(str(weights))
        self.confidence = confidence
        self.class_codes = self._validate_classes(self.model.names)

    @staticmethod
    def _validate_classes(names: Mapping[int, str] | list[str]) -> dict[int, str]:
        items = names.items() if isinstance(names, Mapping) else enumerate(names)
        try:
            normalized = {int(index): normalize_agent_card(name) for index, name in items}
        except (TypeError, ValueError) as exc:
            raise YoloCardConfigurationError(f"Invalid YOLO card class: {exc}") from exc
        if len(normalized) != 52 or len(set(normalized.values())) != 52:
            raise YoloCardConfigurationError(
                "YOLO card model must expose exactly 52 unique playing-card classes."
            )
        return normalized

    def detect(self, frame: np.ndarray) -> tuple[DetectedCard, ...]:
        results = self.model.predict(source=frame, conf=self.confidence, verbose=False)
        if not results:
            return ()
        boxes = results[0].boxes
        xyxy = boxes.xyxy.cpu().tolist()
        confidences = boxes.conf.cpu().tolist()
        classes = boxes.cls.cpu().tolist()
        frame_height, frame_width = frame.shape[:2]
        detections = []
        for bounds, score, class_index in zip(xyxy, confidences, classes):
            left, top, right, bottom = (round(value) for value in bounds)
            left = max(0, min(left, frame_width - 1))
            top = max(0, min(top, frame_height - 1))
            right = max(left + 1, min(right, frame_width))
            bottom = max(top + 1, min(bottom, frame_height))
            roi = Rect(left, top, max(1, right - left), max(1, bottom - top))
            zone = CardZone.MY_HAND if (top + bottom) / 2 >= frame_height * 0.58 else CardZone.TABLE
            detections.append(
                DetectedCard(
                    code=self.class_codes[int(class_index)],
                    roi=roi,
                    zone=zone,
                    confidence=float(score),
                )
            )
        return tuple(detections)
