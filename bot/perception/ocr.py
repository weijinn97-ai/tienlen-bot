from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import cv2
import numpy as np

from contracts.interfaces import Rect


class OcrConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class OcrText:
    text: str
    roi: Rect


class TesseractOcr:
    """Small ROI OCR adapter with injectable engine for deterministic testing."""

    def __init__(self, engine: Callable[..., str] | None = None) -> None:
        if engine is None:
            try:
                import pytesseract
                pytesseract.get_tesseract_version()
            except (ImportError, OSError) as exc:
                raise OcrConfigurationError(
                    "Install pytesseract and the Tesseract executable before enabling OCR."
                ) from exc
            engine = pytesseract.image_to_string
        self.engine = engine

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
        text = self.engine(processed, config=config).strip()
        return OcrText(text=text, roi=roi)
