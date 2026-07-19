"""Lightweight perception components that do not require a trained model."""

from bot.perception.turn_owner import (
    DEFAULT_AVATAR_LAYOUT,
    AvatarRoiLayout,
    CardCountDelta,
    HighlightDetection,
    HybridTurnOwnerDetector,
    HybridTurnOwnerConsensus,
    NormalizedRect,
    TurnOwnerDetection,
    TurnOwnerConsensusResult,
    YellowHighlightDetector,
)
from bot.perception.table_state import (
    StateAcceptancePolicy,
    TableStateAssembler,
    TableStateConsensus,
    TableStateConsensusResult,
)
from bot.perception.buttons import (
    ButtonTemplate,
    TemplateButtonDetector,
    load_gameplay_button_detector,
)
from bot.perception.yolo_cards import YoloCardConfigurationError, YoloCardDetector
from bot.perception.ocr import OcrConfigurationError, OcrText, TesseractOcr
from bot.perception.fan_cards import FanCardTemplateRecognizer, FanGeometry

__all__ = [
    "DEFAULT_AVATAR_LAYOUT",
    "AvatarRoiLayout",
    "ButtonTemplate",
    "FanCardTemplateRecognizer",
    "FanGeometry",
    "CardCountDelta",
    "HighlightDetection",
    "HybridTurnOwnerDetector",
    "HybridTurnOwnerConsensus",
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
    "TurnOwnerConsensusResult",
    "YellowHighlightDetector",
    "YoloCardConfigurationError",
    "YoloCardDetector",
    "load_gameplay_button_detector",
]
