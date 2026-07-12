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

__all__ = [
    "DEFAULT_AVATAR_LAYOUT",
    "AvatarRoiLayout",
    "CardCountDelta",
    "HighlightDetection",
    "HybridTurnOwnerDetector",
    "NormalizedRect",
    "StateAcceptancePolicy",
    "TableStateAssembler",
    "TableStateConsensus",
    "TableStateConsensusResult",
    "TurnOwnerDetection",
    "YellowHighlightDetector",
]
