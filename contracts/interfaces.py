from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Final, Mapping, Sequence


RANK_ORDER: Final[tuple[str, ...]] = (
    "3",
    "4",
    "5",
    "6",
    "7",
    "8",
    "9",
    "10",
    "J",
    "Q",
    "K",
    "A",
    "2",
)
SUIT_ORDER: Final[tuple[str, ...]] = ("S", "C", "D", "H")

_VALID_RANKS: Final[frozenset[str]] = frozenset(RANK_ORDER)
_VALID_SUITS: Final[frozenset[str]] = frozenset(SUIT_ORDER)
_RANK_STRENGTH: Final[dict[str, int]] = {rank: index for index, rank in enumerate(RANK_ORDER)}
_SUIT_STRENGTH: Final[dict[str, int]] = {suit: index for index, suit in enumerate(SUIT_ORDER)}


def _validate_confidence(value: float, *, field_name: str) -> None:
    if value < 0.0 or value > 1.0:
        raise ValueError(f"{field_name} must be within [0.0, 1.0].")


def validate_card_code(card_code: str) -> str:
    """Validate card encoding in the normalized Tien Len format.

    Format: "{rank}{suit}", for example: "3S", "10D", "AH", "2H".
    Suit order is fixed to: S=Spades, C=Clubs, D=Diamonds, H=Hearts.
    Rank order is fixed to: 3<4<...<K<A<2.
    """

    normalized = card_code.strip().upper()
    if len(normalized) < 2:
        raise ValueError(f"Invalid card code: {card_code!r}")

    suit = normalized[-1]
    rank = normalized[:-1]
    if rank not in _VALID_RANKS or suit not in _VALID_SUITS:
        raise ValueError(f"Invalid card code: {card_code!r}")
    return normalized


def card_strength(card_code: str) -> tuple[int, int]:
    normalized = validate_card_code(card_code)
    rank = normalized[:-1]
    suit = normalized[-1]
    return (_RANK_STRENGTH[rank], _SUIT_STRENGTH[suit])


def card_sort_key(card_code: str) -> tuple[int, int]:
    return card_strength(card_code)


def sort_cards(cards: Sequence[str]) -> tuple[str, ...]:
    return tuple(sorted((validate_card_code(card) for card in cards), key=card_sort_key))


class SeatPosition(IntEnum):
    SELF = 0
    LEFT = 1
    TOP = 2
    RIGHT = 3


class GamePhase(str, Enum):
    DEALING = "dealing"
    PLAYING = "playing"
    ENDED = "ended"


class CardZone(str, Enum):
    MY_HAND = "my_hand"
    TABLE = "table"
    SELECTED = "selected"


class ButtonId(str, Enum):
    PLAY = "play"
    PASS = "pass"
    READY = "ready"
    START = "start"
    HINT = "hint"
    UNKNOWN = "unknown"


class ActionKind(str, Enum):
    PLAY = "play"
    PASS = "pass"
    WAIT = "wait"


class VerifyExpectedChange(str, Enum):
    ROI_CHANGED = "roi_changed"
    SELECTION_TOGGLED = "selection_toggled"
    BUTTON_STATE_CHANGED = "button_state_changed"
    CARD_COUNT_DECREASED = "card_count_decreased"


class TurnPrimarySignal(str, Enum):
    AVATAR_TIMER = "avatar_timer"
    AVATAR_HIGHLIGHT = "avatar_highlight"


class TurnSecondarySignal(str, Enum):
    CARD_COUNT_DELTA = "card_count_delta"


class TransitionEvent(str, Enum):
    ROUND_START = "round_start"
    ROUND_END = "round_end"
    MY_TURN = "my_turn"


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    width: int
    height: int

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("Rect width and height must be positive.")
        if self.x < 0 or self.y < 0:
            raise ValueError("Rect coordinates must be non-negative.")


@dataclass(frozen=True)
class DetectedCard:
    code: str
    roi: Rect
    zone: CardZone
    confidence: float
    seat: SeatPosition | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", validate_card_code(self.code))
        _validate_confidence(self.confidence, field_name="confidence")


@dataclass(frozen=True)
class CardCombo:
    cards: tuple[str, ...]
    combo_type: str = "unknown"
    owner: SeatPosition | None = None
    confidence: float = 1.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "cards", sort_cards(self.cards))
        _validate_confidence(self.confidence, field_name="confidence")


@dataclass(frozen=True)
class ButtonState:
    button_id: ButtonId | str
    label: str
    roi: Rect
    is_visible: bool = True
    is_enabled: bool = True
    confidence: float = 1.0

    def __post_init__(self) -> None:
        _validate_confidence(self.confidence, field_name="confidence")


@dataclass(frozen=True)
class TurnOwnerEvidence:
    primary_signal: TurnPrimarySignal
    primary_roi: Rect
    primary_confidence: float
    secondary_signal: TurnSecondarySignal = TurnSecondarySignal.CARD_COUNT_DELTA
    secondary_confidence: float = 0.0
    signals_agree: bool = False
    notes: str = ""

    def __post_init__(self) -> None:
        _validate_confidence(self.primary_confidence, field_name="primary_confidence")
        _validate_confidence(self.secondary_confidence, field_name="secondary_confidence")


@dataclass(frozen=True)
class PerceptionSnapshot:
    bot_id: str
    frame_id: str
    frame_ts: int
    confidence: float
    cards: tuple[DetectedCard, ...] = ()
    player_card_counts: Mapping[SeatPosition, int] = field(default_factory=dict)
    turn_owner: SeatPosition | None = None
    turn_owner_evidence: TurnOwnerEvidence | None = None
    buttons: tuple[ButtonState, ...] = ()
    game_phase: GamePhase = GamePhase.DEALING
    room_id: str | None = None
    round_text: str | None = None

    def __post_init__(self) -> None:
        if not self.bot_id.strip():
            raise ValueError("bot_id must not be empty.")
        if not self.frame_id.strip():
            raise ValueError("frame_id must not be empty.")
        if self.frame_ts <= 0:
            raise ValueError("frame_ts must be positive.")
        _validate_confidence(self.confidence, field_name="confidence")
        for seat, count in self.player_card_counts.items():
            if count < 0 or count > 13:
                raise ValueError(f"player_card_counts[{seat!r}] must be within [0, 13].")


@dataclass(frozen=True)
class TableState:
    frame_id: str
    frame_ts: int
    confidence: float
    my_cards: tuple[str, ...] = ()
    selected_cards: tuple[str, ...] = ()
    last_played_combo: CardCombo | None = None
    player_card_counts: Mapping[SeatPosition, int] = field(default_factory=dict)
    turn_owner: SeatPosition | None = None
    turn_owner_evidence: TurnOwnerEvidence | None = None
    buttons: tuple[ButtonState, ...] = ()
    game_phase: GamePhase = GamePhase.DEALING
    room_id: str | None = None

    def __post_init__(self) -> None:
        if not self.frame_id.strip():
            raise ValueError("frame_id must not be empty.")
        if self.frame_ts <= 0:
            raise ValueError("frame_ts must be positive.")
        _validate_confidence(self.confidence, field_name="confidence")
        object.__setattr__(self, "my_cards", sort_cards(self.my_cards))
        object.__setattr__(self, "selected_cards", sort_cards(self.selected_cards))
        for seat, count in self.player_card_counts.items():
            if count < 0 or count > 13:
                raise ValueError(f"player_card_counts[{seat!r}] must be within [0, 13].")


@dataclass(frozen=True)
class VerifySpec:
    roi: Rect
    expected_change: VerifyExpectedChange
    timeout_ms: int
    max_retries: int
    escalate_to_hand_count: bool = True

    def __post_init__(self) -> None:
        if self.timeout_ms <= 0:
            raise ValueError("timeout_ms must be positive.")
        if self.max_retries < 0:
            raise ValueError("max_retries must be non-negative.")


@dataclass(frozen=True)
class ActionPlan:
    kind: ActionKind
    cards: tuple[str, ...] = ()
    target_button: ButtonId | str | None = None
    verify_spec: VerifySpec | None = None
    confidence: float = 1.0
    reason: str = ""

    def __post_init__(self) -> None:
        _validate_confidence(self.confidence, field_name="confidence")
        object.__setattr__(self, "cards", sort_cards(self.cards))

        if self.kind == ActionKind.PLAY and not self.cards:
            raise ValueError("PLAY actions must include at least one card.")
        if self.kind in {ActionKind.PASS, ActionKind.WAIT} and self.cards:
            raise ValueError(f"{self.kind.value.upper()} actions must not include cards.")


@dataclass(frozen=True)
class ConsensusSpec:
    history_size: int
    required_matches: int
    require_latest_frame: bool = True

    def __post_init__(self) -> None:
        if self.history_size < 1:
            raise ValueError("history_size must be positive.")
        if self.required_matches < 1 or self.required_matches > self.history_size:
            raise ValueError("required_matches must be within history_size.")


REGULAR_ACTION_CONSENSUS: Final[ConsensusSpec] = ConsensusSpec(
    history_size=3,
    required_matches=2,
    require_latest_frame=True,
)
TRANSITION_CONSENSUS: Final[ConsensusSpec] = ConsensusSpec(
    history_size=4,
    required_matches=3,
    require_latest_frame=True,
)
