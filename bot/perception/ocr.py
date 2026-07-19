from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Callable

import cv2
import numpy as np

from contracts.interfaces import Rect


class OcrConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class OcrText:
    text: str
    roi: Rect
    confidence: float

    @property
    def is_unknown(self) -> bool:
        return self.text == "UNKNOWN"


class TesseractOcr:
    """Small ROI OCR adapter with injectable engine for deterministic testing."""

    def __init__(
        self,
        engine: Callable[..., Any] | None = None,
        *,
        minimum_confidence: float = 0.75,
    ) -> None:
        if not 0.0 <= minimum_confidence <= 1.0:
            raise ValueError("minimum_confidence must be within [0.0, 1.0].")
        if engine is None:
            try:
                import pytesseract
                pytesseract.get_tesseract_version()
            except (ImportError, OSError) as exc:
                raise OcrConfigurationError(
                    "Install pytesseract and the Tesseract executable before enabling OCR."
                ) from exc
            engine = lambda image, **kwargs: pytesseract.image_to_data(
                image,
                output_type=pytesseract.Output.DICT,
                **kwargs,
            )
        self.engine = engine
        self.minimum_confidence = minimum_confidence

    def recognize(self, frame: np.ndarray, roi: Rect, *, whitelist: str = "") -> OcrText:
        height, width = frame.shape[:2]
        if roi.x + roi.width > width or roi.y + roi.height > height:
            raise ValueError("OCR ROI is outside the frame.")
        crop = frame[roi.y : roi.y + roi.height, roi.x : roi.x + roi.width, :3]
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        enlarged = cv2.resize(gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
        processed = cv2.threshold(enlarged, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
        config = "--psm 7"
        if whitelist:
            config += f" -c tessedit_char_whitelist={whitelist}"
        raw = self.engine(processed, config=config)
        text, confidence = self._parse_result(raw)
        if not text or confidence < self.minimum_confidence:
            text = "UNKNOWN"
        return OcrText(text=text, roi=roi, confidence=confidence)

    @staticmethod
    def _parse_result(raw: Any) -> tuple[str, float]:
        # String engines remain supported for deterministic tests and custom adapters.
        if isinstance(raw, str):
            text = raw.strip()
            return text, 1.0 if text else 0.0
        if isinstance(raw, tuple) and len(raw) == 2:
            text = str(raw[0]).strip()
            confidence = float(raw[1])
            if not 0.0 <= confidence <= 1.0:
                raise ValueError("OCR confidence must be within [0.0, 1.0].")
            return text, confidence
        if isinstance(raw, Mapping):
            texts = raw.get("text", ())
            confidences = raw.get("conf", ())
            if not isinstance(texts, Sequence) or not isinstance(
                confidences, Sequence
            ):
                raise ValueError("OCR data result must contain text and conf sequences.")
            accepted: list[tuple[str, float]] = []
            for text, confidence in zip(texts, confidences):
                normalized = str(text).strip()
                try:
                    score = float(confidence)
                except (TypeError, ValueError):
                    continue
                if normalized and score >= 0.0:
                    accepted.append((normalized, min(score / 100.0, 1.0)))
            if not accepted:
                return "", 0.0
            return " ".join(text for text, _ in accepted), min(
                score for _, score in accepted
            )
        raise ValueError("Unsupported OCR engine result.")
