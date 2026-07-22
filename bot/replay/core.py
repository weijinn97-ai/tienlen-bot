from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from contracts.interfaces import (
    ButtonId,
    ButtonState,
    CardCombo,
    GamePhase,
    Rect,
    SeatPosition,
    TableState,
    TurnOwnerEvidence,
    TurnPrimarySignal,
)


SCHEMA_VERSION = 1
MAX_REPLAY_BYTES = 16 * 1024 * 1024
REDACTED = "[REDACTED]"
SENSITIVE_KEYS = {
    "account",
    "adb_serial",
    "auth",
    "password",
    "room_id",
    "secret",
    "token",
}
FORBIDDEN_BINARY_KEYS = {"base64", "frame_bytes", "image_bytes", "raw_frame"}


class EventKind(str, Enum):
    FRAME = "frame"
    PERCEPTION = "perception"
    STABLE_STATE = "stable_state"
    LEGAL_MOVES = "legal_moves"
    DECISION = "decision"
    TAP = "tap"
    VERIFICATION = "verification"


class ReplayValidationError(ValueError):
    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        message = code if not detail else f"{code}: {detail}"
        super().__init__(message)


class ReplayMismatchError(ReplayValidationError):
    pass


@dataclass(frozen=True)
class ReplayEvent:
    sequence: int
    kind: EventKind
    frame_ts: int
    payload: Mapping[str, Any]
    previous_hash: str
    event_hash: str


@dataclass(frozen=True)
class ReplayBundle:
    bot_id: str
    session_id: str
    events: tuple[ReplayEvent, ...]
    schema_version: int = SCHEMA_VERSION


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")


def _redact(value: Any, key: str = "") -> Any:
    if key.lower() in SENSITIVE_KEYS:
        return REDACTED
    if isinstance(value, bytes):
        raise ReplayValidationError("binary_payload_forbidden", key or "payload")
    if isinstance(value, Mapping):
        output = {}
        for child_key, child_value in value.items():
            normalized_key = str(child_key)
            if normalized_key.lower() in FORBIDDEN_BINARY_KEYS:
                raise ReplayValidationError("raw_frame_forbidden", normalized_key)
            output[normalized_key] = _redact(child_value, normalized_key)
        return output
    if isinstance(value, (list, tuple)):
        return [_redact(item) for item in value]
    if isinstance(value, Enum):
        return value.value
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise ReplayValidationError("non_json_payload", type(value).__name__)


def _validate_redacted(value: Any, key: str = "") -> None:
    if key.lower() in SENSITIVE_KEYS and value != REDACTED:
        raise ReplayValidationError("unredacted_sensitive_value", key)
    if isinstance(value, Mapping):
        for child_key, child_value in value.items():
            normalized_key = str(child_key)
            if normalized_key.lower() in FORBIDDEN_BINARY_KEYS:
                raise ReplayValidationError("raw_frame_forbidden", normalized_key)
            _validate_redacted(child_value, normalized_key)
    elif isinstance(value, list):
        for item in value:
            _validate_redacted(item)


def _event_material(
    sequence: int,
    kind: EventKind,
    frame_ts: int,
    payload: Mapping[str, Any],
    previous_hash: str,
) -> dict[str, Any]:
    return {
        "frame_ts": frame_ts,
        "kind": kind.value,
        "payload": payload,
        "previous_hash": previous_hash,
        "sequence": sequence,
    }


class ReplayRecorder:
    def __init__(self, bot_id: str, session_id: str) -> None:
        if not bot_id.strip() or not session_id.strip():
            raise ValueError("bot_id and session_id must not be empty.")
        self.bot_id = bot_id
        self.session_id = session_id
        self._events: list[ReplayEvent] = []

    def append(
        self,
        kind: EventKind,
        *,
        frame_ts: int,
        payload: Mapping[str, Any],
    ) -> ReplayEvent:
        if frame_ts <= 0:
            raise ValueError("frame_ts must be positive.")
        sequence = len(self._events)
        previous_hash = self._events[-1].event_hash if self._events else "0" * 64
        safe_payload = _redact(payload)
        material = _event_material(sequence, kind, frame_ts, safe_payload, previous_hash)
        event_hash = hashlib.sha256(_canonical(material)).hexdigest()
        event = ReplayEvent(
            sequence=sequence,
            kind=kind,
            frame_ts=frame_ts,
            payload=safe_payload,
            previous_hash=previous_hash,
            event_hash=event_hash,
        )
        self._events.append(event)
        return event

    def append_table_state(
        self,
        state: TableState,
        *,
        decision_input: Mapping[str, Any] | None = None,
    ) -> ReplayEvent:
        payload: dict[str, Any] = {"table_state": table_state_to_dict(state)}
        if decision_input is not None:
            payload["decision_input"] = decision_input
        return self.append(EventKind.STABLE_STATE, frame_ts=state.frame_ts, payload=payload)

    def bundle(self) -> ReplayBundle:
        return ReplayBundle(self.bot_id, self.session_id, tuple(self._events))

    def write(self, path: Path) -> str:
        document = bundle_to_document(self.bundle())
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(_canonical(document) + b"\n")
        return str(document["bundle_checksum"])


def bundle_to_document(bundle: ReplayBundle) -> dict[str, Any]:
    body = {
        "bot_id": bundle.bot_id,
        "events": [
            {
                **_event_material(
                    event.sequence,
                    event.kind,
                    event.frame_ts,
                    event.payload,
                    event.previous_hash,
                ),
                "event_hash": event.event_hash,
            }
            for event in bundle.events
        ],
        "schema_version": bundle.schema_version,
        "session_id": bundle.session_id,
    }
    return {**body, "bundle_checksum": hashlib.sha256(_canonical(body)).hexdigest()}


def read_bundle(path: Path, *, max_bytes: int = MAX_REPLAY_BYTES) -> ReplayBundle:
    if not path.exists():
        raise ReplayValidationError("replay_missing", str(path))
    if path.stat().st_size > max_bytes:
        raise ReplayValidationError("replay_too_large", str(path.stat().st_size))
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReplayValidationError("invalid_json", type(exc).__name__) from exc
    return document_to_bundle(document)


def document_to_bundle(document: object) -> ReplayBundle:
    if not isinstance(document, dict):
        raise ReplayValidationError("invalid_document", "root must be an object")
    required = {"bot_id", "bundle_checksum", "events", "schema_version", "session_id"}
    if set(document) != required:
        raise ReplayValidationError("invalid_document_fields", str(sorted(set(document))))
    if document["schema_version"] != SCHEMA_VERSION:
        raise ReplayValidationError("unsupported_schema", str(document["schema_version"]))
    body = {key: document[key] for key in required if key != "bundle_checksum"}
    expected_checksum = hashlib.sha256(_canonical(body)).hexdigest()
    if document["bundle_checksum"] != expected_checksum:
        raise ReplayValidationError("bundle_checksum_mismatch")
    if not isinstance(document["events"], list):
        raise ReplayValidationError("invalid_events", "events must be a list")

    events: list[ReplayEvent] = []
    expected_previous = "0" * 64
    for index, raw in enumerate(document["events"]):
        event = _parse_event(raw, index, expected_previous)
        events.append(event)
        expected_previous = event.event_hash
    bot_id = str(document["bot_id"])
    session_id = str(document["session_id"])
    if not bot_id.strip() or not session_id.strip():
        raise ReplayValidationError("empty_identity")
    return ReplayBundle(bot_id, session_id, tuple(events))


def _parse_event(raw: object, index: int, expected_previous: str) -> ReplayEvent:
    fields = {"event_hash", "frame_ts", "kind", "payload", "previous_hash", "sequence"}
    if not isinstance(raw, dict) or set(raw) != fields:
        raise ReplayValidationError("invalid_event_fields", str(index))
    if raw["sequence"] != index:
        raise ReplayValidationError("invalid_sequence", str(index))
    if raw["previous_hash"] != expected_previous:
        raise ReplayValidationError("hash_chain_mismatch", str(index))
    try:
        kind = EventKind(raw["kind"])
    except ValueError as exc:
        raise ReplayValidationError("unknown_event_kind", str(raw["kind"])) from exc
    if not isinstance(raw["frame_ts"], int) or raw["frame_ts"] <= 0:
        raise ReplayValidationError("invalid_frame_ts", str(index))
    if not isinstance(raw["payload"], dict):
        raise ReplayValidationError("invalid_payload", str(index))
    _validate_redacted(raw["payload"])
    material = _event_material(index, kind, raw["frame_ts"], raw["payload"], expected_previous)
    expected_hash = hashlib.sha256(_canonical(material)).hexdigest()
    if raw["event_hash"] != expected_hash:
        raise ReplayValidationError("event_hash_mismatch", str(index))
    return ReplayEvent(
        index,
        kind,
        raw["frame_ts"],
        raw["payload"],
        expected_previous,
        expected_hash,
    )


def reproduce_decisions(
    bundle: ReplayBundle,
    decide: Callable[[Mapping[str, Any]], Mapping[str, Any]],
) -> int:
    verified = 0
    pending_input: Mapping[str, Any] | None = None
    for event in bundle.events:
        if event.kind == EventKind.STABLE_STATE:
            candidate = event.payload.get("decision_input")
            pending_input = candidate if isinstance(candidate, Mapping) else None
        elif event.kind == EventKind.DECISION and pending_input is not None:
            expected = event.payload.get("result")
            actual = _redact(decide(pending_input))
            if actual != expected:
                raise ReplayMismatchError(
                    "decision_mismatch",
                    f"sequence={event.sequence}; expected={expected!r}; actual={actual!r}",
                )
            verified += 1
            pending_input = None
    return verified


def table_state_to_dict(state: TableState) -> dict[str, Any]:
    combo = None
    if state.last_played_combo is not None:
        combo = {
            "cards": list(state.last_played_combo.cards),
            "combo_type": state.last_played_combo.combo_type,
            "confidence": state.last_played_combo.confidence,
            "owner": state.last_played_combo.owner.name if state.last_played_combo.owner is not None else None,
        }
    evidence = None
    if state.turn_owner_evidence is not None:
        item = state.turn_owner_evidence
        evidence = {
            "notes": item.notes,
            "primary_confidence": item.primary_confidence,
            "primary_roi": vars(item.primary_roi),
            "primary_signal": item.primary_signal.value,
            "secondary_confidence": item.secondary_confidence,
            "signals_agree": item.signals_agree,
        }
    return {
        "buttons": [
            {
                "button_id": button.button_id.value if isinstance(button.button_id, Enum) else button.button_id,
                "confidence": button.confidence,
                "is_enabled": button.is_enabled,
                "is_visible": button.is_visible,
                "label": button.label,
                "roi": vars(button.roi),
            }
            for button in state.buttons
        ],
        "confidence": state.confidence,
        "frame_id": state.frame_id,
        "frame_ts": state.frame_ts,
        "game_phase": state.game_phase.value,
        "last_played_combo": combo,
        "my_cards": list(state.my_cards),
        "player_card_counts": {seat.name: count for seat, count in state.player_card_counts.items()},
        "room_id": state.room_id,
        "selected_cards": list(state.selected_cards),
        "turn_owner": state.turn_owner.name if state.turn_owner is not None else None,
        "turn_owner_evidence": evidence,
    }


def table_state_from_dict(value: Mapping[str, Any]) -> TableState:
    combo_value = value.get("last_played_combo")
    combo = None
    if isinstance(combo_value, Mapping):
        owner = combo_value.get("owner")
        combo = CardCombo(
            cards=tuple(combo_value["cards"]),
            combo_type=str(combo_value["combo_type"]),
            confidence=float(combo_value["confidence"]),
            owner=SeatPosition[str(owner)] if owner is not None else None,
        )
    evidence_value = value.get("turn_owner_evidence")
    evidence = None
    if isinstance(evidence_value, Mapping):
        roi = evidence_value["primary_roi"]
        evidence = TurnOwnerEvidence(
            primary_signal=TurnPrimarySignal(evidence_value["primary_signal"]),
            primary_roi=Rect(**roi),
            primary_confidence=float(evidence_value["primary_confidence"]),
            secondary_confidence=float(evidence_value["secondary_confidence"]),
            signals_agree=bool(evidence_value["signals_agree"]),
            notes=str(evidence_value["notes"]),
        )
    buttons = []
    for item in value.get("buttons", []):
        button_id_value = item["button_id"]
        try:
            button_id: ButtonId | str = ButtonId(button_id_value)
        except ValueError:
            button_id = str(button_id_value)
        buttons.append(
            ButtonState(
                button_id=button_id,
                label=str(item["label"]),
                roi=Rect(**item["roi"]),
                is_visible=bool(item["is_visible"]),
                is_enabled=bool(item["is_enabled"]),
                confidence=float(item["confidence"]),
            )
        )
    turn_owner = value.get("turn_owner")
    return TableState(
        frame_id=str(value["frame_id"]),
        frame_ts=int(value["frame_ts"]),
        confidence=float(value["confidence"]),
        my_cards=tuple(value.get("my_cards", [])),
        selected_cards=tuple(value.get("selected_cards", [])),
        last_played_combo=combo,
        player_card_counts={
            SeatPosition[str(seat)]: int(count)
            for seat, count in value.get("player_card_counts", {}).items()
        },
        turn_owner=SeatPosition[str(turn_owner)] if turn_owner is not None else None,
        turn_owner_evidence=evidence,
        buttons=tuple(buttons),
        game_phase=GamePhase(value["game_phase"]),
        room_id=value.get("room_id"),
    )
