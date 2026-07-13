"""Lightweight perception components that do not require a trained model."""

from bot.perception.turn_owner import (
    DEFAULT_AVATAR_LAYOUT,
    AvatarRoiLayout,
    CardCountDelta,
    HighlightDetection,
    HybridTurnOwnerDetector,
    NormalizedRect,
    TurnOwnerDetection,
    YellowHighlightDetector,
)
from bot.perception.table_state import (
    StateAcceptancePolicy,
    TableStateAssembler,
    TableStateConsensus,
    TableStateConsensusResult,
)
from bot.perception.buttons import ButtonTemplate, TemplateButtonDetector
from bot.perception.yolo_cards import YoloCardConfigurationError, YoloCardDetector
from bot.perception.ocr import OcrConfigurationError, OcrText, TesseractOcr

__all__ = [
    "DEFAULT_AVATAR_LAYOUT",
    "AvatarRoiLayout",
    "ButtonTemplate",
    "CardCountDelta",
    "HighlightDetection",
    "HybridTurnOwnerDetector",
    "NormalizedRect",
    "OcrConfigurationError",
    "OcrText",
    "StateAcceptancePolicy",
    "TableStateAssembler",
    "TableStateConsensus",
    "TableStateConsensusResult",
    "TemplateButtonDetector",
    "TesseractOcr",
    "TurnOwnerDetection",
    "YellowHighlightDetector",
    "YoloCardConfigurationError",
    "YoloCardDetector",
]
