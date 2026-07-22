"""Stable serialization and deserialization for contract types.

This module provides canonical JSON round-trip for every public contract
dataclass.  The wire format uses an envelope with ``schema_version``,
``contract_type`` and ``payload`` keys.  Enums are serialized by their
``.value``; tuples are preserved through a list→tuple restore; mappings
with enum keys use stable string keys derived from the enum value.

No pickle, eval, dynamic import or arbitrary class construction is used.
Unknown schema versions, unknown contract types, missing fields, extra
fields and invalid values all raise explicit exceptions.
"""

from __future__ import annotations

import json
from enum import Enum
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
# Enum helpers
# ---------------------------------------------------------------------------

_ENUM_BY_NAME: dict[str, type] = {
    "SeatPosition": SeatPosition,
    "GamePhase": GamePhase,
    "CardZone": CardZone,
    "ButtonId": ButtonId,
    "ActionKind": ActionKind,
    "VerifyExpectedChange": VerifyExpectedChange,
    "TurnPrimarySignal": TurnPrimarySignal,
    "TurnSecondarySignal": TurnSecondarySignal,
}


def _enum_to_value(e: Enum) -> Any:
    """Serialize an enum member by its value."""
    return e.value


def _enum_from_value(enum_cls: type, raw: Any) -> Any:
    """Restore an enum member from its serialized value."""
    try:
        return enum_cls(raw)
    except (ValueError, KeyError):
        raise ValueError(
            f"Invalid value {raw!r} for enum {enum_cls.__name__}"
        ) from None


# ---------------------------------------------------------------------------
# Payload serializers  (contract instance → plain dict)
# ---------------------------------------------------------------------------


def _rect_to_payload(r: Rect) -> dict[str, Any]:
    return {"x": r.x, "y": r.y, "width": r.width, "height": r.height}


def _detected_card_to_payload(c: DetectedCard) -> dict[str, Any]:
    d: dict[str, Any] = {
        "code": c.code,
        "roi": _rect_to_payload(c.roi),
        "zone": _enum_to_value(c.zone),
        "confidence": c.confidence,
    }
    d["seat"] = _enum_to_value(c.seat) if c.seat is not None else None
    return d


def _card_combo_to_payload(cc: CardCombo) -> dict[str, Any]:
    return {
        "cards": list(cc.cards),
        "combo_type": cc.combo_type,
        "owner": _enum_to_value(cc.owner) if cc.owner is not None else None,
        "confidence": cc.confidence,
    }


def _button_state_to_payload(bs: ButtonState) -> dict[str, Any]:
    bid = bs.button_id
    if isinstance(bid, ButtonId):
        bid_val = _enum_to_value(bid)
    else:
        bid_val = str(bid)
    return {
        "button_id": bid_val,
        "label": bs.label,
        "roi": _rect_to_payload(bs.roi),
        "is_visible": bs.is_visible,
        "is_enabled": bs.is_enabled,
        "confidence": bs.confidence,
    }


def _turn_evidence_to_payload(te: TurnOwnerEvidence) -> dict[str, Any]:
    return {
        "primary_signal": _enum_to_value(te.primary_signal),
        "primary_roi": _rect_to_payload(te.primary_roi),
        "primary_confidence": te.primary_confidence,
        "secondary_signal": _enum_to_value(te.secondary_signal),
        "secondary_confidence": te.secondary_confidence,
        "signals_agree": te.signals_agree,
        "notes": te.notes,
    }


def _seat_counts_to_payload(
    counts: Any,
) -> dict[str, int]:
    """Convert SeatPosition→int mapping to stable string keys."""
    return {str(_enum_to_value(seat)): count for seat, count in counts.items()}


def _perception_snapshot_to_payload(ps: PerceptionSnapshot) -> dict[str, Any]:
    return {
        "bot_id": ps.bot_id,
        "frame_id": ps.frame_id,
        "frame_ts": ps.frame_ts,
        "confidence": ps.confidence,
        "cards": [_detected_card_to_payload(c) for c in ps.cards],
        "player_card_counts": _seat_counts_to_payload(ps.player_card_counts),
        "turn_owner": _enum_to_value(ps.turn_owner) if ps.turn_owner is not None else None,
        "turn_owner_evidence": (
            _turn_evidence_to_payload(ps.turn_owner_evidence)
            if ps.turn_owner_evidence is not None
            else None
        ),
        "buttons": [_button_state_to_payload(b) for b in ps.buttons],
        "game_phase": _enum_to_value(ps.game_phase),
        "room_id": ps.room_id,
        "round_text": ps.round_text,
    }


def _table_state_to_payload(ts: TableState) -> dict[str, Any]:
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
        "player_card_counts": _seat_counts_to_payload(ts.player_card_counts),
        "turn_owner": _enum_to_value(ts.turn_owner) if ts.turn_owner is not None else None,
        "turn_owner_evidence": (
            _turn_evidence_to_payload(ts.turn_owner_evidence)
            if ts.turn_owner_evidence is not None
            else None
        ),
        "buttons": [_button_state_to_payload(b) for b in ts.buttons],
        "game_phase": _enum_to_value(ts.game_phase),
        "room_id": ts.room_id,
    }


def _verify_spec_to_payload(vs: VerifySpec) -> dict[str, Any]:
    return {
        "roi": _rect_to_payload(vs.roi),
        "expected_change": _enum_to_value(vs.expected_change),
        "timeout_ms": vs.timeout_ms,
        "max_retries": vs.max_retries,
        "escalate_to_hand_count": vs.escalate_to_hand_count,
    }


def _action_plan_to_payload(ap: ActionPlan) -> dict[str, Any]:
    tb = ap.target_button
    if isinstance(tb, ButtonId):
        tb_val = _enum_to_value(tb)
    elif tb is not None:
        tb_val = str(tb)
    else:
        tb_val = None
    return {
        "kind": _enum_to_value(ap.kind),
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
# Payload deserializers  (plain dict → contract instance)
# ---------------------------------------------------------------------------


def _require_keys(data: dict, keys: set[str], type_name: str) -> None:
    """Validate that *data* has exactly the expected keys."""
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
    "primary_signal", "primary_roi", "primary_confidence",
    "secondary_signal", "secondary_confidence", "signals_agree", "notes",
}
_PERCEPTION_SNAPSHOT_KEYS = {
    "bot_id", "frame_id", "frame_ts", "confidence", "cards",
    "player_card_counts", "turn_owner", "turn_owner_evidence",
    "buttons", "game_phase", "room_id", "round_text",
}
_TABLE_STATE_KEYS = {
    "frame_id", "frame_ts", "confidence", "my_cards", "selected_cards",
    "last_played_combo", "player_card_counts", "turn_owner",
    "turn_owner_evidence", "buttons", "game_phase", "room_id",
}
_VERIFY_SPEC_KEYS = {"roi", "expected_change", "timeout_ms", "max_retries", "escalate_to_hand_count"}
_ACTION_PLAN_KEYS = {"kind", "cards", "target_button", "verify_spec", "confidence", "reason"}
_CONSENSUS_SPEC_KEYS = {"history_size", "required_matches", "require_latest_frame"}


def _rect_from_payload(d: dict) -> Rect:
    _require_keys(d, _RECT_KEYS, "Rect")
    return Rect(x=d["x"], y=d["y"], width=d["width"], height=d["height"])


def _seat_counts_from_payload(d: dict) -> dict[SeatPosition, int]:
    """Restore {SeatPosition: int} from string-keyed dict."""
    result: dict[SeatPosition, int] = {}
    for k, v in d.items():
        seat = _enum_from_value(SeatPosition, int(k))
        if not isinstance(v, int) or v < 0 or v > 13:
            raise ValueError(f"player_card_counts[{k}]: invalid count {v!r}")
        result[seat] = v
    return result


def _detected_card_from_payload(d: dict) -> DetectedCard:
    _require_keys(d, _DETECTED_CARD_KEYS, "DetectedCard")
    return DetectedCard(
        code=validate_card_code(d["code"]),
        roi=_rect_from_payload(d["roi"]),
        zone=_enum_from_value(CardZone, d["zone"]),
        confidence=d["confidence"],
        seat=_enum_from_value(SeatPosition, d["seat"]) if d["seat"] is not None else None,
    )


def _card_combo_from_payload(d: dict) -> CardCombo:
    _require_keys(d, _CARD_COMBO_KEYS, "CardCombo")
    return CardCombo(
        cards=tuple(validate_card_code(c) for c in d["cards"]),
        combo_type=d["combo_type"],
        owner=_enum_from_value(SeatPosition, d["owner"]) if d["owner"] is not None else None,
        confidence=d["confidence"],
    )


def _button_state_from_payload(d: dict) -> ButtonState:
    _require_keys(d, _BUTTON_STATE_KEYS, "ButtonState")
    raw_bid = d["button_id"]
    try:
        bid: ButtonId | str = _enum_from_value(ButtonId, raw_bid)
    except ValueError:
        bid = str(raw_bid)
    return ButtonState(
        button_id=bid,
        label=d["label"],
        roi=_rect_from_payload(d["roi"]),
        is_visible=d["is_visible"],
        is_enabled=d["is_enabled"],
        confidence=d["confidence"],
    )


def _turn_evidence_from_payload(d: dict) -> TurnOwnerEvidence:
    _require_keys(d, _TURN_EVIDENCE_KEYS, "TurnOwnerEvidence")
    return TurnOwnerEvidence(
        primary_signal=_enum_from_value(TurnPrimarySignal, d["primary_signal"]),
        primary_roi=_rect_from_payload(d["primary_roi"]),
        primary_confidence=d["primary_confidence"],
        secondary_signal=_enum_from_value(TurnSecondarySignal, d["secondary_signal"]),
        secondary_confidence=d["secondary_confidence"],
        signals_agree=d["signals_agree"],
        notes=d["notes"],
    )


def _perception_snapshot_from_payload(d: dict) -> PerceptionSnapshot:
    _require_keys(d, _PERCEPTION_SNAPSHOT_KEYS, "PerceptionSnapshot")
    return PerceptionSnapshot(
        bot_id=d["bot_id"],
        frame_id=d["frame_id"],
        frame_ts=d["frame_ts"],
        confidence=d["confidence"],
        cards=tuple(_detected_card_from_payload(c) for c in d["cards"]),
        player_card_counts=_seat_counts_from_payload(d["player_card_counts"]),
        turn_owner=(
            _enum_from_value(SeatPosition, d["turn_owner"])
            if d["turn_owner"] is not None
            else None
        ),
        turn_owner_evidence=(
            _turn_evidence_from_payload(d["turn_owner_evidence"])
            if d["turn_owner_evidence"] is not None
            else None
        ),
        buttons=tuple(_button_state_from_payload(b) for b in d["buttons"]),
        game_phase=_enum_from_value(GamePhase, d["game_phase"]),
        room_id=d["room_id"],
        round_text=d["round_text"],
    )


def _table_state_from_payload(d: dict) -> TableState:
    _require_keys(d, _TABLE_STATE_KEYS, "TableState")
    return TableState(
        frame_id=d["frame_id"],
        frame_ts=d["frame_ts"],
        confidence=d["confidence"],
        my_cards=tuple(validate_card_code(c) for c in d["my_cards"]),
        selected_cards=tuple(validate_card_code(c) for c in d["selected_cards"]),
        last_played_combo=(
            _card_combo_from_payload(d["last_played_combo"])
            if d["last_played_combo"] is not None
            else None
        ),
        player_card_counts=_seat_counts_from_payload(d["player_card_counts"]),
        turn_owner=(
            _enum_from_value(SeatPosition, d["turn_owner"])
            if d["turn_owner"] is not None
            else None
        ),
        turn_owner_evidence=(
            _turn_evidence_from_payload(d["turn_owner_evidence"])
            if d["turn_owner_evidence"] is not None
            else None
        ),
        buttons=tuple(_button_state_from_payload(b) for b in d["buttons"]),
        game_phase=_enum_from_value(GamePhase, d["game_phase"]),
        room_id=d["room_id"],
    )


def _verify_spec_from_payload(d: dict) -> VerifySpec:
    _require_keys(d, _VERIFY_SPEC_KEYS, "VerifySpec")
    return VerifySpec(
        roi=_rect_from_payload(d["roi"]),
        expected_change=_enum_from_value(VerifyExpectedChange, d["expected_change"]),
        timeout_ms=d["timeout_ms"],
        max_retries=d["max_retries"],
        escalate_to_hand_count=d["escalate_to_hand_count"],
    )


def _action_plan_from_payload(d: dict) -> ActionPlan:
    _require_keys(d, _ACTION_PLAN_KEYS, "ActionPlan")
    raw_tb = d["target_button"]
    if raw_tb is not None:
        try:
            tb: ButtonId | str | None = _enum_from_value(ButtonId, raw_tb)
        except ValueError:
            tb = str(raw_tb)
    else:
        tb = None
    return ActionPlan(
        kind=_enum_from_value(ActionKind, d["kind"]),
        cards=tuple(validate_card_code(c) for c in d["cards"]),
        target_button=tb,
        verify_spec=(
            _verify_spec_from_payload(d["verify_spec"])
            if d["verify_spec"] is not None
            else None
        ),
        confidence=d["confidence"],
        reason=d["reason"],
    )


def _consensus_spec_from_payload(d: dict) -> ConsensusSpec:
    _require_keys(d, _CONSENSUS_SPEC_KEYS, "ConsensusSpec")
    return ConsensusSpec(
        history_size=d["history_size"],
        required_matches=d["required_matches"],
        require_latest_frame=d["require_latest_frame"],
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
    return {
        "schema_version": CONTRACT_SCHEMA_VERSION,
        "contract_type": type_name,
        "payload": serializer(value),
    }


def contract_from_dict(
    data: dict[str, Any],
) -> ContractType:
    """Deserialize an envelope dict into a contract instance.

    Raises ``ValueError`` for unknown schema versions, unknown contract
    types, missing or extra fields and invalid values.  Raises
    ``TypeError`` if *data* is not a dict.
    """
    if not isinstance(data, dict):
        raise TypeError(f"Expected dict envelope, got {type(data).__name__}")

    envelope_keys = set(data.keys())
    expected_envelope_keys = {"schema_version", "contract_type", "payload"}
    missing = expected_envelope_keys - envelope_keys
    extra = envelope_keys - expected_envelope_keys
    if missing:
        raise ValueError(f"Envelope missing fields: {sorted(missing)}")
    if extra:
        raise ValueError(f"Envelope has unexpected fields: {sorted(extra)}")

    version = data["schema_version"]
    if version != CONTRACT_SCHEMA_VERSION:
        raise ValueError(
            f"Unknown schema_version {version!r}; "
            f"expected {CONTRACT_SCHEMA_VERSION}"
        )

    type_name = data["contract_type"]
    deserializer = _FROM_PAYLOAD.get(type_name)
    if deserializer is None:
        raise ValueError(f"Unknown contract_type: {type_name!r}")

    payload = data["payload"]
    if not isinstance(payload, dict):
        raise TypeError(
            f"Expected dict payload for {type_name}, "
            f"got {type(payload).__name__}"
        )

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


def contract_from_json(document: str) -> ContractType:
    """Deserialize canonical JSON into a contract instance.

    Raises ``json.JSONDecodeError`` for malformed JSON, then delegates
    validation to :func:`contract_from_dict`.
    """
    data = json.loads(document)
    return contract_from_dict(data)
