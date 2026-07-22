"""Stable serialization and deserialization for contract types.

This module provides canonical JSON round-trip for every public contract
dataclass. The wire format uses an envelope with ``schema_version``,
``contract_type`` and ``payload`` keys. Enums are serialized by their
``.value``; tuples are preserved through a list→tuple restore; mappings
with enum keys use stable string keys derived from the enum value.

No pickle, eval, dynamic import or arbitrary class construction is used.
Unknown schema versions, unknown contract types, missing fields, extra
fields and invalid values all raise explicit exceptions.
"""

from __future__ import annotations

import json
import math
from enum import Enum, IntEnum
from typing import Any, Union

from contracts.interfaces import (
    ActionKind,
    ActionPlan,
    ButtonId,
    ButtonState,
    CardCombo,
    CardZone,
    ConsensusSpec,
    DetectedCard,
    GamePhase,
    PerceptionSnapshot,
    Rect,
    SeatPosition,
    TableState,
    TurnOwnerEvidence,
    TurnPrimarySignal,
    TurnSecondarySignal,
    VerifyExpectedChange,
    VerifySpec,
    validate_card_code,
)

# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

CONTRACT_SCHEMA_VERSION: int = 1

# ---------------------------------------------------------------------------
# Type registry
# ---------------------------------------------------------------------------

_CONTRACT_TYPE_NAME: dict[type, str] = {
    Rect: "Rect",
    DetectedCard: "DetectedCard",
    CardCombo: "CardCombo",
    ButtonState: "ButtonState",
    TurnOwnerEvidence: "TurnOwnerEvidence",
    PerceptionSnapshot: "PerceptionSnapshot",
    TableState: "TableState",
    VerifySpec: "VerifySpec",
    ActionPlan: "ActionPlan",
    ConsensusSpec: "ConsensusSpec",
}

_CONTRACT_TYPE_BY_NAME: dict[str, type] = {v: k for k, v in _CONTRACT_TYPE_NAME.items()}

# ---------------------------------------------------------------------------
# Type validation helpers
# ---------------------------------------------------------------------------


def _require_dict(val: Any, field_name: str) -> dict[str, Any]:
    if type(val) is not dict:
        raise TypeError(f"{field_name} must be a dict, got {type(val).__name__}")
    return val


def _require_list(val: Any, field_name: str) -> list[Any]:
    if type(val) is not list:
        raise TypeError(f"{field_name} must be a list, got {type(val).__name__}")
    return val


def _require_str(val: Any, field_name: str) -> str:
    if type(val) is not str:
        raise TypeError(f"{field_name} must be a str, got {type(val).__name__}")
    return val


def _require_int(val: Any, field_name: str) -> int:
    if type(val) is not int:
        raise TypeError(f"{field_name} must be an int, got {type(val).__name__}")
    return val


def _require_bool(val: Any, field_name: str) -> bool:
    if type(val) is not bool:
        raise TypeError(f"{field_name} must be a bool, got {type(val).__name__}")
    return val


def _require_confidence(val: Any, field_name: str) -> float:
    if type(val) is bool or not isinstance(val, (int, float)):
        raise TypeError(f"{field_name} must be a float or int, got {type(val).__name__}")
    fval = float(val)
    if not math.isfinite(fval):
        raise ValueError(f"{field_name} must be a finite real number, got {val!r}")
    if not 0.0 <= fval <= 1.0:
        raise ValueError(f"{field_name} must be within [0.0, 1.0], got {fval}")
    return fval


def _require_tuple(val: Any, field_name: str) -> tuple[Any, ...]:
    if type(val) is not tuple:
        raise TypeError(f"{field_name} must be exactly tuple, got {type(val).__name__}")
    return val


def _require_contract(val: Any, expected_cls: type, field_name: str) -> Any:
    if type(val) is not expected_cls:
        raise TypeError(f"{field_name} must be exactly {expected_cls.__name__}, got {type(val).__name__}")
    return val

# ---------------------------------------------------------------------------
# Enum helpers
# ---------------------------------------------------------------------------


def _enum_to_value(e: Any, expected_cls: type, field_name: str) -> Any:
    """Serialize an enum member by its value, requiring exact type match."""
    if type(e) is not expected_cls:
        raise TypeError(f"{field_name} must be exactly {expected_cls.__name__}, got {type(e).__name__}")
    return e.value


def _enum_from_value(enum_cls: type, raw: Any) -> Any:
    """Restore an enum member from its serialized value."""
    if issubclass(enum_cls, IntEnum):
        if type(raw) is not int:
            raise TypeError(f"Invalid type {type(raw).__name__} for IntEnum {enum_cls.__name__}")
    elif issubclass(enum_cls, Enum):
        if type(raw) is not str:
            raise TypeError(f"Invalid type {type(raw).__name__} for Enum {enum_cls.__name__}")
    try:
        return enum_cls(raw)
    except (ValueError, KeyError):
        raise ValueError(
            f"Invalid value {raw!r} for enum {enum_cls.__name__}"
        ) from None


def _parse_button_id(val: Any, field_name: str) -> ButtonId | str:
    if type(val) is not str:
        raise TypeError(f"{field_name} must be a string, got {type(val).__name__}")
    try:
        return ButtonId(val)
    except ValueError:
        return val


def _parse_target_button(val: Any, field_name: str) -> ButtonId | str | None:
    if val is None:
        return None
    if type(val) is not str:
        raise TypeError(f"{field_name} must be a string or None, got {type(val).__name__}")
    try:
        return ButtonId(val)
    except ValueError:
        return val


# ---------------------------------------------------------------------------
# Payload serializers (contract instance → plain dict)
# ---------------------------------------------------------------------------


def _rect_to_payload(r: Rect) -> dict[str, Any]:
    _require_contract(r, Rect, "Rect")
    return {"x": r.x, "y": r.y, "width": r.width, "height": r.height}


def _detected_card_to_payload(c: DetectedCard) -> dict[str, Any]:
    _require_contract(c, DetectedCard, "DetectedCard")
    d: dict[str, Any] = {
        "code": c.code,
        "roi": _rect_to_payload(c.roi),
        "zone": _enum_to_value(c.zone, CardZone, "DetectedCard.zone"),
        "confidence": c.confidence,
    }
    d["seat"] = _enum_to_value(c.seat, SeatPosition, "DetectedCard.seat") if c.seat is not None else None
    return d


def _card_combo_to_payload(cc: CardCombo) -> dict[str, Any]:
    _require_contract(cc, CardCombo, "CardCombo")
    _require_tuple(cc.cards, "CardCombo.cards")
    return {
        "cards": list(cc.cards),
        "combo_type": cc.combo_type,
        "owner": _enum_to_value(cc.owner, SeatPosition, "CardCombo.owner") if cc.owner is not None else None,
        "confidence": cc.confidence,
    }


def _button_state_to_payload(bs: ButtonState) -> dict[str, Any]:
    _require_contract(bs, ButtonState, "ButtonState")
    bid = bs.button_id
    if type(bid) is ButtonId:
        bid_val = _enum_to_value(bid, ButtonId, "ButtonState.button_id")
    elif type(bid) is str:
        bid_val = bid
    else:
        raise TypeError(f"ButtonState.button_id must be exactly ButtonId or str, got {type(bid).__name__}")
    return {
        "button_id": bid_val,
        "label": bs.label,
        "roi": _rect_to_payload(bs.roi),
        "is_visible": bs.is_visible,
        "is_enabled": bs.is_enabled,
        "confidence": bs.confidence,
    }


def _turn_evidence_to_payload(te: TurnOwnerEvidence) -> dict[str, Any]:
    _require_contract(te, TurnOwnerEvidence, "TurnOwnerEvidence")
    return {
        "primary_signal": _enum_to_value(te.primary_signal, TurnPrimarySignal, "TurnOwnerEvidence.primary_signal"),
        "primary_roi": _rect_to_payload(te.primary_roi),
        "primary_confidence": te.primary_confidence,
        "secondary_signal": _enum_to_value(te.secondary_signal, TurnSecondarySignal, "TurnOwnerEvidence.secondary_signal"),
        "secondary_confidence": te.secondary_confidence,
        "signals_agree": te.signals_agree,
        "notes": te.notes,
    }


def _seat_counts_to_payload(counts: Any, field_name: str) -> dict[str, int]:
    """Convert SeatPosition→int mapping to stable string keys."""
    if not hasattr(counts, "items"):
        raise TypeError(f"{field_name} must be a mapping, got {type(counts).__name__}")
    res: dict[str, int] = {}
    for seat, count in counts.items():
        if type(seat) is not SeatPosition:
            raise TypeError(f"{field_name} keys must be exactly SeatPosition, got {type(seat).__name__}")
        if type(count) is not int:
            raise TypeError(f"{field_name}[{seat}] count must be exact int, got {type(count).__name__}")
        if count < 0 or count > 13:
            raise ValueError(f"{field_name}[{seat}] count must be in [0, 13], got {count}")
        res[str(_enum_to_value(seat, SeatPosition, f"{field_name} key"))] = count
    return res


def _perception_snapshot_to_payload(ps: PerceptionSnapshot) -> dict[str, Any]:
    _require_contract(ps, PerceptionSnapshot, "PerceptionSnapshot")
    _require_tuple(ps.cards, "PerceptionSnapshot.cards")
    _require_tuple(ps.buttons, "PerceptionSnapshot.buttons")
    return {
        "bot_id": ps.bot_id,
        "frame_id": ps.frame_id,
        "frame_ts": ps.frame_ts,
        "confidence": ps.confidence,
        "cards": [_detected_card_to_payload(c) for c in ps.cards],
        "player_card_counts": _seat_counts_to_payload(ps.player_card_counts, "PerceptionSnapshot.player_card_counts"),
        "turn_owner": _enum_to_value(ps.turn_owner, SeatPosition, "PerceptionSnapshot.turn_owner") if ps.turn_owner is not None else None,
        "turn_owner_evidence": (
            _turn_evidence_to_payload(ps.turn_owner_evidence)
            if ps.turn_owner_evidence is not None
            else None
        ),
        "buttons": [_button_state_to_payload(b) for b in ps.buttons],
        "game_phase": _enum_to_value(ps.game_phase, GamePhase, "PerceptionSnapshot.game_phase"),
        "room_id": ps.room_id,
        "round_text": ps.round_text,
    }


def _table_state_to_payload(ts: TableState) -> dict[str, Any]:
    _require_contract(ts, TableState, "TableState")
    _require_tuple(ts.my_cards, "TableState.my_cards")
    _require_tuple(ts.selected_cards, "TableState.selected_cards")
    _require_tuple(ts.buttons, "TableState.buttons")
    return {
        "frame_id": ts.frame_id,
        "frame_ts": ts.frame_ts,
        "confidence": ts.confidence,
        "my_cards": list(ts.my_cards),
        "selected_cards": list(ts.selected_cards),
        "last_played_combo": (
            _card_combo_to_payload(ts.last_played_combo)
            if ts.last_played_combo is not None
            else None
        ),
        "player_card_counts": _seat_counts_to_payload(ts.player_card_counts, "TableState.player_card_counts"),
        "turn_owner": _enum_to_value(ts.turn_owner, SeatPosition, "TableState.turn_owner") if ts.turn_owner is not None else None,
        "turn_owner_evidence": (
            _turn_evidence_to_payload(ts.turn_owner_evidence)
            if ts.turn_owner_evidence is not None
            else None
        ),
        "buttons": [_button_state_to_payload(b) for b in ts.buttons],
        "game_phase": _enum_to_value(ts.game_phase, GamePhase, "TableState.game_phase"),
        "room_id": ts.room_id,
    }


def _verify_spec_to_payload(vs: VerifySpec) -> dict[str, Any]:
    _require_contract(vs, VerifySpec, "VerifySpec")
    return {
        "roi": _rect_to_payload(vs.roi),
        "expected_change": _enum_to_value(vs.expected_change, VerifyExpectedChange, "VerifySpec.expected_change"),
        "timeout_ms": vs.timeout_ms,
        "max_retries": vs.max_retries,
        "escalate_to_hand_count": vs.escalate_to_hand_count,
    }


def _action_plan_to_payload(ap: ActionPlan) -> dict[str, Any]:
    _require_contract(ap, ActionPlan, "ActionPlan")
    _require_tuple(ap.cards, "ActionPlan.cards")
    tb = ap.target_button
    if tb is None:
        tb_val = None
    elif type(tb) is ButtonId:
        tb_val = _enum_to_value(tb, ButtonId, "ActionPlan.target_button")
    elif type(tb) is str:
        tb_val = tb
    else:
        raise TypeError(f"ActionPlan.target_button must be ButtonId, str, or None, got {type(tb).__name__}")
    return {
        "kind": _enum_to_value(ap.kind, ActionKind, "ActionPlan.kind"),
        "cards": list(ap.cards),
        "target_button": tb_val,
        "verify_spec": (
            _verify_spec_to_payload(ap.verify_spec)
            if ap.verify_spec is not None
            else None
        ),
        "confidence": ap.confidence,
        "reason": ap.reason,
    }


def _consensus_spec_to_payload(cs: ConsensusSpec) -> dict[str, Any]:
    _require_contract(cs, ConsensusSpec, "ConsensusSpec")
    return {
        "history_size": cs.history_size,
        "required_matches": cs.required_matches,
        "require_latest_frame": cs.require_latest_frame,
    }


_TO_PAYLOAD = {
    Rect: _rect_to_payload,
    DetectedCard: _detected_card_to_payload,
    CardCombo: _card_combo_to_payload,
    ButtonState: _button_state_to_payload,
    TurnOwnerEvidence: _turn_evidence_to_payload,
    PerceptionSnapshot: _perception_snapshot_to_payload,
    TableState: _table_state_to_payload,
    VerifySpec: _verify_spec_to_payload,
    ActionPlan: _action_plan_to_payload,
    ConsensusSpec: _consensus_spec_to_payload,
}

# ---------------------------------------------------------------------------
# Payload deserializers (plain dict → contract instance)
# ---------------------------------------------------------------------------


def _require_keys(data: dict, keys: set[str], type_name: str) -> None:
    """Validate that *data* has exactly the expected keys."""
    for k in data.keys():
        if type(k) is not str:
            raise TypeError(f"{type_name}: dict key must be str, got {type(k).__name__}")
    actual = set(data.keys())
    missing = keys - actual
    extra = actual - keys
    if missing:
        raise ValueError(f"{type_name}: missing fields {sorted(missing)}")
    if extra:
        raise ValueError(f"{type_name}: unexpected fields {sorted(extra)}")


_RECT_KEYS = {"x", "y", "width", "height"}
_DETECTED_CARD_KEYS = {"code", "roi", "zone", "confidence", "seat"}
_CARD_COMBO_KEYS = {"cards", "combo_type", "owner", "confidence"}
_BUTTON_STATE_KEYS = {"button_id", "label", "roi", "is_visible", "is_enabled", "confidence"}
_TURN_EVIDENCE_KEYS = {
    "primary_signal",
    "primary_roi",
    "primary_confidence",
    "secondary_signal",
    "secondary_confidence",
    "signals_agree",
    "notes",
}
_PERCEPTION_SNAPSHOT_KEYS = {
    "bot_id",
    "frame_id",
    "frame_ts",
    "confidence",
    "cards",
    "player_card_counts",
    "turn_owner",
    "turn_owner_evidence",
    "buttons",
    "game_phase",
    "room_id",
    "round_text",
}
_TABLE_STATE_KEYS = {
    "frame_id",
    "frame_ts",
    "confidence",
    "my_cards",
    "selected_cards",
    "last_played_combo",
    "player_card_counts",
    "turn_owner",
    "turn_owner_evidence",
    "buttons",
    "game_phase",
    "room_id",
}
_VERIFY_SPEC_KEYS = {
    "roi",
    "expected_change",
    "timeout_ms",
    "max_retries",
    "escalate_to_hand_count",
}
_ACTION_PLAN_KEYS = {"kind", "cards", "target_button", "verify_spec", "confidence", "reason"}
_CONSENSUS_SPEC_KEYS = {"history_size", "required_matches", "require_latest_frame"}


def _rect_from_payload(d: Any) -> Rect:
    _require_dict(d, "Rect")
    _require_keys(d, _RECT_KEYS, "Rect")
    return Rect(
        x=_require_int(d["x"], "Rect.x"),
        y=_require_int(d["y"], "Rect.y"),
        width=_require_int(d["width"], "Rect.width"),
        height=_require_int(d["height"], "Rect.height"),
    )


def _seat_counts_from_payload(d: Any) -> dict[SeatPosition, int]:
    """Restore {SeatPosition: int} from string-keyed dict."""
    _require_dict(d, "player_card_counts")
    result: dict[SeatPosition, int] = {}
    valid_keys = {"0", "1", "2", "3"}
    for k, v in d.items():
        if type(k) is not str or k not in valid_keys:
            raise ValueError(f"player_card_counts: invalid seat key {k!r}")
        if type(v) is not int:
            raise TypeError(f"player_card_counts[{k}]: count must be int, got {type(v).__name__}")
        if v < 0 or v > 13:
            raise ValueError(f"player_card_counts[{k}]: count must be in [0, 13], got {v}")
        seat = SeatPosition(int(k))
        if seat in result:
            raise ValueError(f"player_card_counts: duplicate seat {seat!r}")
        result[seat] = v
    return result


def _detected_card_from_payload(d: Any) -> DetectedCard:
    _require_dict(d, "DetectedCard")
    _require_keys(d, _DETECTED_CARD_KEYS, "DetectedCard")
    return DetectedCard(
        code=validate_card_code(_require_str(d["code"], "DetectedCard.code")),
        roi=_rect_from_payload(d["roi"]),
        zone=_enum_from_value(CardZone, d["zone"]),
        confidence=_require_confidence(d["confidence"], "DetectedCard.confidence"),
        seat=_enum_from_value(SeatPosition, d["seat"]) if d["seat"] is not None else None,
    )


def _card_combo_from_payload(d: Any) -> CardCombo:
    _require_dict(d, "CardCombo")
    _require_keys(d, _CARD_COMBO_KEYS, "CardCombo")
    cards_list = _require_list(d["cards"], "CardCombo.cards")
    return CardCombo(
        cards=tuple(validate_card_code(_require_str(c, "CardCombo.cards item")) for c in cards_list),
        combo_type=_require_str(d["combo_type"], "CardCombo.combo_type"),
        owner=_enum_from_value(SeatPosition, d["owner"]) if d["owner"] is not None else None,
        confidence=_require_confidence(d["confidence"], "CardCombo.confidence"),
    )


def _button_state_from_payload(d: Any) -> ButtonState:
    _require_dict(d, "ButtonState")
    _require_keys(d, _BUTTON_STATE_KEYS, "ButtonState")
    return ButtonState(
        button_id=_parse_button_id(d["button_id"], "ButtonState.button_id"),
        label=_require_str(d["label"], "ButtonState.label"),
        roi=_rect_from_payload(d["roi"]),
        is_visible=_require_bool(d["is_visible"], "ButtonState.is_visible"),
        is_enabled=_require_bool(d["is_enabled"], "ButtonState.is_enabled"),
        confidence=_require_confidence(d["confidence"], "ButtonState.confidence"),
    )


def _turn_evidence_from_payload(d: Any) -> TurnOwnerEvidence:
    _require_dict(d, "TurnOwnerEvidence")
    _require_keys(d, _TURN_EVIDENCE_KEYS, "TurnOwnerEvidence")
    return TurnOwnerEvidence(
        primary_signal=_enum_from_value(TurnPrimarySignal, d["primary_signal"]),
        primary_roi=_rect_from_payload(d["primary_roi"]),
        primary_confidence=_require_confidence(d["primary_confidence"], "TurnOwnerEvidence.primary_confidence"),
        secondary_signal=_enum_from_value(TurnSecondarySignal, d["secondary_signal"]),
        secondary_confidence=_require_confidence(d["secondary_confidence"], "TurnOwnerEvidence.secondary_confidence"),
        signals_agree=_require_bool(d["signals_agree"], "TurnOwnerEvidence.signals_agree"),
        notes=_require_str(d["notes"], "TurnOwnerEvidence.notes"),
    )


def _perception_snapshot_from_payload(d: Any) -> PerceptionSnapshot:
    _require_dict(d, "PerceptionSnapshot")
    _require_keys(d, _PERCEPTION_SNAPSHOT_KEYS, "PerceptionSnapshot")
    cards_list = _require_list(d["cards"], "PerceptionSnapshot.cards")
    buttons_list = _require_list(d["buttons"], "PerceptionSnapshot.buttons")
    return PerceptionSnapshot(
        bot_id=_require_str(d["bot_id"], "PerceptionSnapshot.bot_id"),
        frame_id=_require_str(d["frame_id"], "PerceptionSnapshot.frame_id"),
        frame_ts=_require_int(d["frame_ts"], "PerceptionSnapshot.frame_ts"),
        confidence=_require_confidence(d["confidence"], "PerceptionSnapshot.confidence"),
        cards=tuple(_detected_card_from_payload(c) for c in cards_list),
        player_card_counts=_seat_counts_from_payload(d["player_card_counts"]),
        turn_owner=_enum_from_value(SeatPosition, d["turn_owner"]) if d["turn_owner"] is not None else None,
        turn_owner_evidence=(
            _turn_evidence_from_payload(d["turn_owner_evidence"])
            if d["turn_owner_evidence"] is not None
            else None
        ),
        buttons=tuple(_button_state_from_payload(b) for b in buttons_list),
        game_phase=_enum_from_value(GamePhase, d["game_phase"]),
        room_id=_require_str(d["room_id"], "PerceptionSnapshot.room_id") if d["room_id"] is not None else None,
        round_text=_require_str(d["round_text"], "PerceptionSnapshot.round_text") if d["round_text"] is not None else None,
    )


def _table_state_from_payload(d: Any) -> TableState:
    _require_dict(d, "TableState")
    _require_keys(d, _TABLE_STATE_KEYS, "TableState")
    my_cards_list = _require_list(d["my_cards"], "TableState.my_cards")
    selected_cards_list = _require_list(d["selected_cards"], "TableState.selected_cards")
    buttons_list = _require_list(d["buttons"], "TableState.buttons")
    return TableState(
        frame_id=_require_str(d["frame_id"], "TableState.frame_id"),
        frame_ts=_require_int(d["frame_ts"], "TableState.frame_ts"),
        confidence=_require_confidence(d["confidence"], "TableState.confidence"),
        my_cards=tuple(validate_card_code(_require_str(c, "TableState.my_cards item")) for c in my_cards_list),
        selected_cards=tuple(validate_card_code(_require_str(c, "TableState.selected_cards item")) for c in selected_cards_list),
        last_played_combo=(
            _card_combo_from_payload(d["last_played_combo"])
            if d["last_played_combo"] is not None
            else None
        ),
        player_card_counts=_seat_counts_from_payload(d["player_card_counts"]),
        turn_owner=_enum_from_value(SeatPosition, d["turn_owner"]) if d["turn_owner"] is not None else None,
        turn_owner_evidence=(
            _turn_evidence_from_payload(d["turn_owner_evidence"])
            if d["turn_owner_evidence"] is not None
            else None
        ),
        buttons=tuple(_button_state_from_payload(b) for b in buttons_list),
        game_phase=_enum_from_value(GamePhase, d["game_phase"]),
        room_id=_require_str(d["room_id"], "TableState.room_id") if d["room_id"] is not None else None,
    )


def _verify_spec_from_payload(d: Any) -> VerifySpec:
    _require_dict(d, "VerifySpec")
    _require_keys(d, _VERIFY_SPEC_KEYS, "VerifySpec")
    return VerifySpec(
        roi=_rect_from_payload(d["roi"]),
        expected_change=_enum_from_value(VerifyExpectedChange, d["expected_change"]),
        timeout_ms=_require_int(d["timeout_ms"], "VerifySpec.timeout_ms"),
        max_retries=_require_int(d["max_retries"], "VerifySpec.max_retries"),
        escalate_to_hand_count=_require_bool(d["escalate_to_hand_count"], "VerifySpec.escalate_to_hand_count"),
    )


def _action_plan_from_payload(d: Any) -> ActionPlan:
    _require_dict(d, "ActionPlan")
    _require_keys(d, _ACTION_PLAN_KEYS, "ActionPlan")
    cards_list = _require_list(d["cards"], "ActionPlan.cards")
    return ActionPlan(
        kind=_enum_from_value(ActionKind, d["kind"]),
        cards=tuple(validate_card_code(_require_str(c, "ActionPlan.cards item")) for c in cards_list),
        target_button=_parse_target_button(d["target_button"], "ActionPlan.target_button"),
        verify_spec=(
            _verify_spec_from_payload(d["verify_spec"])
            if d["verify_spec"] is not None
            else None
        ),
        confidence=_require_confidence(d["confidence"], "ActionPlan.confidence"),
        reason=_require_str(d["reason"], "ActionPlan.reason"),
    )


def _consensus_spec_from_payload(d: Any) -> ConsensusSpec:
    _require_dict(d, "ConsensusSpec")
    _require_keys(d, _CONSENSUS_SPEC_KEYS, "ConsensusSpec")
    return ConsensusSpec(
        history_size=_require_int(d["history_size"], "ConsensusSpec.history_size"),
        required_matches=_require_int(d["required_matches"], "ConsensusSpec.required_matches"),
        require_latest_frame=_require_bool(d["require_latest_frame"], "ConsensusSpec.require_latest_frame"),
    )


_FROM_PAYLOAD: dict[str, Any] = {
    "Rect": _rect_from_payload,
    "DetectedCard": _detected_card_from_payload,
    "CardCombo": _card_combo_from_payload,
    "ButtonState": _button_state_from_payload,
    "TurnOwnerEvidence": _turn_evidence_from_payload,
    "PerceptionSnapshot": _perception_snapshot_from_payload,
    "TableState": _table_state_from_payload,
    "VerifySpec": _verify_spec_from_payload,
    "ActionPlan": _action_plan_from_payload,
    "ConsensusSpec": _consensus_spec_from_payload,
}

# ---------------------------------------------------------------------------
# Supported contract union (for type hints)
# ---------------------------------------------------------------------------

ContractType = Union[
    Rect,
    DetectedCard,
    CardCombo,
    ButtonState,
    TurnOwnerEvidence,
    PerceptionSnapshot,
    TableState,
    VerifySpec,
    ActionPlan,
    ConsensusSpec,
]

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def contract_to_dict(value: ContractType) -> dict[str, Any]:
    """Serialize a contract instance into an envelope dict.

    The envelope contains ``schema_version``, ``contract_type`` and
    ``payload``.
    """
    cls = type(value)
    type_name = _CONTRACT_TYPE_NAME.get(cls)
    if type_name is None:
        raise TypeError(f"Unsupported contract type: {cls.__name__}")
    serializer = _TO_PAYLOAD[cls]
    payload = serializer(value)

    # Validate generated payload using matching deserializer to enforce
    # strict wire validation on serialization output as well
    deserializer = _FROM_PAYLOAD[type_name]
    deserializer(payload)

    return {
        "schema_version": CONTRACT_SCHEMA_VERSION,
        "contract_type": type_name,
        "payload": payload,
    }


def contract_from_dict(
    data: dict[str, Any],
) -> ContractType:
    """Deserialize an envelope dict into a contract instance.

    Raises ``ValueError`` for unknown schema versions, unknown contract
    types, missing or extra fields and invalid values. Raises
    ``TypeError`` if *data* is not a dict.
    """
    if type(data) is not dict:
        raise TypeError(f"Expected dict envelope, got {type(data).__name__}")

    for k in data.keys():
        if type(k) is not str:
            raise TypeError(f"Envelope key must be str, got {type(k).__name__}")

    envelope_keys = set(data.keys())
    expected_envelope_keys = {"schema_version", "contract_type", "payload"}
    missing = expected_envelope_keys - envelope_keys
    extra = envelope_keys - expected_envelope_keys
    if missing:
        raise ValueError(f"Envelope missing fields: {sorted(missing)}")
    if extra:
        raise ValueError(f"Envelope has unexpected fields: {sorted(extra)}")

    version = data["schema_version"]
    if type(version) is not int:
        raise TypeError(f"schema_version must be an int, got {type(version).__name__}")
    if version != CONTRACT_SCHEMA_VERSION:
        raise ValueError(
            f"Unknown schema_version {version!r}; "
            f"expected {CONTRACT_SCHEMA_VERSION}"
        )

    type_name = _require_str(data["contract_type"], "contract_type")
    deserializer = _FROM_PAYLOAD.get(type_name)
    if deserializer is None:
        raise ValueError(f"Unknown contract_type: {type_name!r}")

    payload = _require_dict(data["payload"], f"payload for {type_name}")

    return deserializer(payload)


def contract_to_json(value: ContractType) -> str:
    """Serialize a contract instance to canonical JSON.

    The output is UTF-8 safe, deterministic (sorted keys, no trailing
    whitespace), and free of NaN/Infinity.
    """
    envelope = contract_to_dict(value)
    return json.dumps(
        envelope,
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    )


def _reject_json_constant(val: str) -> None:
    raise ValueError(f"Non-finite JSON constant not allowed: {val!r}")


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    res: dict[str, Any] = {}
    for k, v in pairs:
        if type(k) is str and k in res:
            raise ValueError(f"Duplicate JSON key: {k!r}")
        res[k] = v
    return res


def contract_from_json(document: str) -> ContractType:
    """Deserialize canonical JSON into a contract instance.

    Raises ``json.JSONDecodeError`` for malformed JSON, then delegates
    validation to :func:`contract_from_dict`.
    """
    if type(document) is not str:
        raise TypeError(f"document must be a str, got {type(document).__name__}")
    data = json.loads(
        document,
        parse_constant=_reject_json_constant,
        object_pairs_hook=_reject_duplicate_json_keys,
    )
    return contract_from_dict(data)
