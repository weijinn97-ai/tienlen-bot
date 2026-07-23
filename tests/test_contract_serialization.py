"""Comprehensive tests for contracts.serialization module.

Covers:
- Round-trip for every required contract type
- Canonical deterministic JSON
- Fixture compatibility (read from disk, no rewrite)
- Nested enum / mapping / tuple preservation
- Malformed JSON
- Unknown schema / type
- Missing / extra fields
- Invalid card / count / confidence / enum values
- Consumer smoke with GameStateAdapter, replay table_state_to_dict/from_dict
"""

from __future__ import annotations

import json
import os
import unittest
from pathlib import Path

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
)
from contracts.serialization import (
    CONTRACT_SCHEMA_VERSION,
    contract_from_dict,
    contract_from_json,
    contract_to_dict,
    contract_to_json,
)

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "contracts_v1"


# -----------------------------------------------------------------------
# helpers
# -----------------------------------------------------------------------

def _sample_rect() -> Rect:
    return Rect(x=10, y=20, width=30, height=40)


def _sample_detected_card() -> DetectedCard:
    return DetectedCard(
        code="AH",
        roi=_sample_rect(),
        zone=CardZone.MY_HAND,
        confidence=0.99,
        seat=SeatPosition.SELF,
    )


def _sample_card_combo() -> CardCombo:
    return CardCombo(
        cards=("10C", "10D"),
        combo_type="pair",
        owner=SeatPosition.LEFT,
        confidence=0.96,
    )


def _sample_button_state() -> ButtonState:
    return ButtonState(
        button_id=ButtonId.PLAY,
        label="Danh",
        roi=_sample_rect(),
        is_visible=True,
        is_enabled=True,
        confidence=0.98,
    )


def _sample_turn_evidence() -> TurnOwnerEvidence:
    return TurnOwnerEvidence(
        primary_signal=TurnPrimarySignal.AVATAR_HIGHLIGHT,
        primary_roi=_sample_rect(),
        primary_confidence=0.92,
        secondary_signal=TurnSecondarySignal.CARD_COUNT_DELTA,
        secondary_confidence=0.85,
        signals_agree=True,
        notes="test note",
    )


def _sample_perception_snapshot() -> PerceptionSnapshot:
    return PerceptionSnapshot(
        bot_id="bot-001",
        frame_id="frame-001",
        frame_ts=1700000000000,
        confidence=0.95,
        cards=(_sample_detected_card(),),
        player_card_counts={SeatPosition.SELF: 10, SeatPosition.LEFT: 8},
        turn_owner=SeatPosition.SELF,
        turn_owner_evidence=_sample_turn_evidence(),
        buttons=(_sample_button_state(),),
        game_phase=GamePhase.PLAYING,
        room_id="room-001",
        round_text="Round 1",
    )


def _sample_table_state() -> TableState:
    return TableState(
        frame_id="frame-002",
        frame_ts=1700000001000,
        confidence=0.93,
        my_cards=("3S", "AH"),
        selected_cards=("AH",),
        last_played_combo=_sample_card_combo(),
        player_card_counts={SeatPosition.SELF: 2, SeatPosition.LEFT: 7},
        turn_owner=SeatPosition.SELF,
        turn_owner_evidence=_sample_turn_evidence(),
        buttons=(_sample_button_state(),),
        game_phase=GamePhase.PLAYING,
        room_id="room-002",
    )


def _sample_verify_spec() -> VerifySpec:
    return VerifySpec(
        roi=_sample_rect(),
        expected_change=VerifyExpectedChange.CARD_COUNT_DECREASED,
        timeout_ms=3000,
        max_retries=2,
        escalate_to_hand_count=True,
    )


def _sample_action_plan_play() -> ActionPlan:
    return ActionPlan(
        kind=ActionKind.PLAY,
        cards=("QH", "QD"),
        target_button=ButtonId.PLAY,
        verify_spec=_sample_verify_spec(),
        confidence=0.95,
        reason="pair of queens",
    )


def _sample_action_plan_wait() -> ActionPlan:
    return ActionPlan(
        kind=ActionKind.WAIT,
        confidence=1.0,
        reason="not my turn",
    )


def _sample_consensus_spec() -> ConsensusSpec:
    return ConsensusSpec(
        history_size=3,
        required_matches=2,
        require_latest_frame=True,
    )


# -----------------------------------------------------------------------
# Round-trip tests for every required type
# -----------------------------------------------------------------------


class RoundTripTests(unittest.TestCase):
    """Test that each contract type survives serialize → deserialize."""

    def _round_trip(self, original: object) -> None:
        envelope = contract_to_dict(original)
        self.assertEqual(envelope["schema_version"], CONTRACT_SCHEMA_VERSION)
        restored = contract_from_dict(envelope)
        self.assertEqual(original, restored)

    def test_rect_round_trip(self) -> None:
        self._round_trip(_sample_rect())

    def test_detected_card_round_trip(self) -> None:
        self._round_trip(_sample_detected_card())

    def test_card_combo_round_trip(self) -> None:
        self._round_trip(_sample_card_combo())

    def test_button_state_round_trip(self) -> None:
        self._round_trip(_sample_button_state())

    def test_turn_owner_evidence_round_trip(self) -> None:
        self._round_trip(_sample_turn_evidence())

    def test_perception_snapshot_round_trip(self) -> None:
        self._round_trip(_sample_perception_snapshot())

    def test_table_state_round_trip(self) -> None:
        self._round_trip(_sample_table_state())

    def test_verify_spec_round_trip(self) -> None:
        self._round_trip(_sample_verify_spec())

    def test_action_plan_play_round_trip(self) -> None:
        self._round_trip(_sample_action_plan_play())

    def test_action_plan_wait_round_trip(self) -> None:
        self._round_trip(_sample_action_plan_wait())

    def test_consensus_spec_round_trip(self) -> None:
        self._round_trip(_sample_consensus_spec())

    def test_json_round_trip_matches_dict_round_trip(self) -> None:
        """contract_to_json → contract_from_json equals dict round-trip."""
        for obj in (
            _sample_rect(),
            _sample_detected_card(),
            _sample_card_combo(),
            _sample_button_state(),
            _sample_turn_evidence(),
            _sample_perception_snapshot(),
            _sample_table_state(),
            _sample_verify_spec(),
            _sample_action_plan_play(),
            _sample_action_plan_wait(),
            _sample_consensus_spec(),
        ):
            with self.subTest(type=type(obj).__name__):
                j = contract_to_json(obj)
                restored = contract_from_json(j)
                self.assertEqual(obj, restored)


# -----------------------------------------------------------------------
# Canonical deterministic JSON
# -----------------------------------------------------------------------


class CanonicalJsonTests(unittest.TestCase):
    """Verify byte-for-byte determinism of JSON output."""

    def test_same_object_produces_identical_bytes(self) -> None:
        obj = _sample_perception_snapshot()
        j1 = contract_to_json(obj)
        j2 = contract_to_json(obj)
        self.assertEqual(j1, j2, "Canonical JSON must be deterministic")

    def test_sorted_keys_in_output(self) -> None:
        obj = _sample_table_state()
        j = contract_to_json(obj)
        parsed = json.loads(j)
        self.assertEqual(list(parsed.keys()), sorted(parsed.keys()))

    def test_no_whitespace_in_canonical_output(self) -> None:
        """Canonical JSON uses no spaces/newlines for compactness."""
        j = contract_to_json(_sample_rect())
        self.assertNotIn("\n", j)
        # No space after ':' or ',' (compact separators)
        self.assertNotIn(": ", j)
        self.assertNotIn(", ", j)


# -----------------------------------------------------------------------
# Nested enum, mapping with enum keys, tuple preservation
# -----------------------------------------------------------------------


class NestedDataTests(unittest.TestCase):
    """Verify nested enums, enum-keyed mappings and tuples."""

    def test_enum_key_mapping_round_trip(self) -> None:
        """SeatPosition→int mapping must survive serialization."""
        ts = _sample_table_state()
        j = contract_to_json(ts)
        restored = contract_from_json(j)
        self.assertIsInstance(restored, TableState)
        for seat in restored.player_card_counts:
            self.assertIsInstance(seat, SeatPosition)
        self.assertEqual(ts.player_card_counts, restored.player_card_counts)

    def test_tuple_fields_preserved(self) -> None:
        ts = _sample_table_state()
        restored = contract_from_json(contract_to_json(ts))
        self.assertIsInstance(restored.my_cards, tuple)
        self.assertIsInstance(restored.selected_cards, tuple)
        self.assertIsInstance(restored.buttons, tuple)

    def test_nested_enum_in_detected_card(self) -> None:
        dc = _sample_detected_card()
        restored = contract_from_json(contract_to_json(dc))
        self.assertIsInstance(restored.zone, CardZone)
        self.assertIsInstance(restored.seat, SeatPosition)

    def test_nested_optional_none_fields(self) -> None:
        """DetectedCard with seat=None round-trips correctly."""
        dc = DetectedCard(
            code="3S",
            roi=_sample_rect(),
            zone=CardZone.TABLE,
            confidence=0.95,
            seat=None,
        )
        restored = contract_from_json(contract_to_json(dc))
        self.assertIsNone(restored.seat)

    def test_button_id_string_passthrough(self) -> None:
        """ButtonState with non-enum string button_id survives."""
        bs = ButtonState(
            button_id="custom_button",
            label="Custom",
            roi=_sample_rect(),
            is_visible=True,
            is_enabled=False,
            confidence=0.80,
        )
        restored = contract_from_json(contract_to_json(bs))
        self.assertEqual(restored.button_id, "custom_button")

    def test_action_plan_target_button_string(self) -> None:
        """ActionPlan with non-enum target_button survives."""
        ap = ActionPlan(
            kind=ActionKind.WAIT,
            confidence=0.9,
            reason="waiting",
        )
        restored = contract_from_json(contract_to_json(ap))
        self.assertIsNone(restored.target_button)


# -----------------------------------------------------------------------
# Fixture compatibility tests
# -----------------------------------------------------------------------


class FixtureCompatibilityTests(unittest.TestCase):
    """Read fixtures from disk, deserialize, re-serialize, compare."""

    def _load_fixture(self, filename: str) -> str:
        path = FIXTURES_DIR / filename
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def _assert_fixture_round_trip(self, filename: str) -> None:
        raw = self._load_fixture(filename)
        obj = contract_from_json(raw)
        reserialized = contract_to_json(obj)
        self.assertEqual(raw, reserialized,
                         f"Fixture {filename} did not survive round-trip")

    def test_perception_snapshot_fixture(self) -> None:
        self._assert_fixture_round_trip("perception_snapshot_full.json")

    def test_table_state_fixture(self) -> None:
        self._assert_fixture_round_trip("table_state_full.json")

    def test_action_plan_play_fixture(self) -> None:
        self._assert_fixture_round_trip("action_plan_play.json")

    def test_action_plan_wait_fixture(self) -> None:
        self._assert_fixture_round_trip("action_plan_wait.json")

    def test_perception_snapshot_fixture_has_expected_fields(self) -> None:
        raw = self._load_fixture("perception_snapshot_full.json")
        obj = contract_from_json(raw)
        self.assertIsInstance(obj, PerceptionSnapshot)
        self.assertTrue(len(obj.cards) > 0)
        self.assertTrue(len(obj.buttons) > 0)
        self.assertIsNotNone(obj.turn_owner_evidence)

    def test_table_state_fixture_has_expected_fields(self) -> None:
        raw = self._load_fixture("table_state_full.json")
        obj = contract_from_json(raw)
        self.assertIsInstance(obj, TableState)
        self.assertIsNotNone(obj.last_played_combo)
        self.assertTrue(len(obj.my_cards) > 0)


# -----------------------------------------------------------------------
# Error handling: malformed JSON
# -----------------------------------------------------------------------


class MalformedJsonTests(unittest.TestCase):
    """Verify explicit errors for bad input."""

    def test_malformed_json_raises(self) -> None:
        with self.assertRaises(json.JSONDecodeError):
            contract_from_json("{not valid json}")

    def test_empty_string_raises(self) -> None:
        with self.assertRaises(json.JSONDecodeError):
            contract_from_json("")

    def test_non_dict_raises(self) -> None:
        with self.assertRaises(TypeError):
            contract_from_json("[1,2,3]")


# -----------------------------------------------------------------------
# Error handling: unknown schema / type
# -----------------------------------------------------------------------


class UnknownSchemaTypeTests(unittest.TestCase):
    """Verify rejection of unknown schemas and types."""

    def test_unknown_schema_version(self) -> None:
        envelope = {
            "schema_version": 999,
            "contract_type": "Rect",
            "payload": {"x": 0, "y": 0, "width": 1, "height": 1},
        }
        with self.assertRaises(ValueError) as cm:
            contract_from_dict(envelope)
        self.assertIn("999", str(cm.exception))

    def test_unknown_contract_type(self) -> None:
        envelope = {
            "schema_version": CONTRACT_SCHEMA_VERSION,
            "contract_type": "NonExistentType",
            "payload": {},
        }
        with self.assertRaises(ValueError) as cm:
            contract_from_dict(envelope)
        self.assertIn("NonExistentType", str(cm.exception))

    def test_unsupported_python_type_raises_type_error(self) -> None:
        with self.assertRaises(TypeError):
            contract_to_dict("not a contract")


# -----------------------------------------------------------------------
# Error handling: missing / extra fields
# -----------------------------------------------------------------------


class MissingExtraFieldTests(unittest.TestCase):
    """Verify explicit rejection of wrong field sets."""

    def test_missing_field_in_rect(self) -> None:
        envelope = {
            "schema_version": CONTRACT_SCHEMA_VERSION,
            "contract_type": "Rect",
            "payload": {"x": 0, "y": 0, "width": 1},
        }
        with self.assertRaises(ValueError) as cm:
            contract_from_dict(envelope)
        self.assertIn("missing", str(cm.exception).lower())

    def test_extra_field_in_rect(self) -> None:
        envelope = {
            "schema_version": CONTRACT_SCHEMA_VERSION,
            "contract_type": "Rect",
            "payload": {"x": 0, "y": 0, "width": 1, "height": 1, "extra": 42},
        }
        with self.assertRaises(ValueError) as cm:
            contract_from_dict(envelope)
        self.assertIn("unexpected", str(cm.exception).lower())

    def test_missing_envelope_field(self) -> None:
        data = {"schema_version": 1, "contract_type": "Rect"}
        with self.assertRaises(ValueError) as cm:
            contract_from_dict(data)
        self.assertIn("missing", str(cm.exception).lower())

    def test_extra_envelope_field(self) -> None:
        data = {
            "schema_version": 1,
            "contract_type": "Rect",
            "payload": {"x": 0, "y": 0, "width": 1, "height": 1},
            "bonus": True,
        }
        with self.assertRaises(ValueError) as cm:
            contract_from_dict(data)
        self.assertIn("unexpected", str(cm.exception).lower())

    def test_missing_field_in_action_plan(self) -> None:
        envelope = {
            "schema_version": CONTRACT_SCHEMA_VERSION,
            "contract_type": "ActionPlan",
            "payload": {"kind": "play", "cards": ["3S"]},
        }
        with self.assertRaises(ValueError) as cm:
            contract_from_dict(envelope)
        self.assertIn("missing", str(cm.exception).lower())


# -----------------------------------------------------------------------
# Error handling: invalid card / count / confidence / enum
# -----------------------------------------------------------------------


class InvalidValueTests(unittest.TestCase):
    """Verify rejection of semantically invalid values."""

    def test_invalid_card_code_in_detected_card(self) -> None:
        envelope = {
            "schema_version": CONTRACT_SCHEMA_VERSION,
            "contract_type": "DetectedCard",
            "payload": {
                "code": "ZZ",
                "roi": {"x": 0, "y": 0, "width": 1, "height": 1},
                "zone": "my_hand",
                "confidence": 0.9,
                "seat": None,
            },
        }
        with self.assertRaises(ValueError):
            contract_from_dict(envelope)

    def test_invalid_confidence_in_card_combo(self) -> None:
        envelope = {
            "schema_version": CONTRACT_SCHEMA_VERSION,
            "contract_type": "CardCombo",
            "payload": {
                "cards": ["3S"],
                "combo_type": "single",
                "owner": None,
                "confidence": 1.5,
            },
        }
        with self.assertRaises(ValueError):
            contract_from_dict(envelope)

    def test_invalid_enum_value_in_game_phase(self) -> None:
        ts_envelope = contract_to_dict(_sample_table_state())
        ts_envelope["payload"]["game_phase"] = "invalid_phase"
        with self.assertRaises(ValueError):
            contract_from_dict(ts_envelope)

    def test_invalid_seat_in_player_card_counts(self) -> None:
        ts_envelope = contract_to_dict(_sample_table_state())
        ts_envelope["payload"]["player_card_counts"]["99"] = 5
        with self.assertRaises(ValueError):
            contract_from_dict(ts_envelope)

    def test_negative_count_in_player_card_counts(self) -> None:
        ts_envelope = contract_to_dict(_sample_table_state())
        ts_envelope["payload"]["player_card_counts"]["0"] = -1
        with self.assertRaises(ValueError):
            contract_from_dict(ts_envelope)

    def test_count_over_thirteen_rejected(self) -> None:
        ts_envelope = contract_to_dict(_sample_table_state())
        ts_envelope["payload"]["player_card_counts"]["0"] = 14
        with self.assertRaises(ValueError):
            contract_from_dict(ts_envelope)

    def test_invalid_card_in_action_plan(self) -> None:
        envelope = {
            "schema_version": CONTRACT_SCHEMA_VERSION,
            "contract_type": "ActionPlan",
            "payload": {
                "kind": "play",
                "cards": ["INVALID"],
                "target_button": "play",
                "verify_spec": None,
                "confidence": 0.9,
                "reason": "test",
            },
        }
        with self.assertRaises(ValueError):
            contract_from_dict(envelope)

    def test_invalid_expected_change_enum(self) -> None:
        envelope = {
            "schema_version": CONTRACT_SCHEMA_VERSION,
            "contract_type": "VerifySpec",
            "payload": {
                "roi": {"x": 0, "y": 0, "width": 1, "height": 1},
                "expected_change": "nonexistent_change",
                "timeout_ms": 1000,
                "max_retries": 1,
                "escalate_to_hand_count": True,
            },
        }
        with self.assertRaises(ValueError):
            contract_from_dict(envelope)

    def test_negative_rect_dimension_rejected(self) -> None:
        envelope = {
            "schema_version": CONTRACT_SCHEMA_VERSION,
            "contract_type": "Rect",
            "payload": {"x": 0, "y": 0, "width": -1, "height": 1},
        }
        with self.assertRaises(ValueError):
            contract_from_dict(envelope)

    def test_zero_timeout_ms_rejected(self) -> None:
        envelope = {
            "schema_version": CONTRACT_SCHEMA_VERSION,
            "contract_type": "VerifySpec",
            "payload": {
                "roi": {"x": 0, "y": 0, "width": 1, "height": 1},
                "expected_change": "roi_changed",
                "timeout_ms": 0,
                "max_retries": 1,
                "escalate_to_hand_count": True,
            },
        }
        with self.assertRaises(ValueError):
            contract_from_dict(envelope)


# -----------------------------------------------------------------------
# Mandatory strict wire validation regression tests (Repair Spec Section 4)
# -----------------------------------------------------------------------


class StrictWireValidationTests(unittest.TestCase):
    """Regression tests required by repair spec Section 4."""

    def test_json_non_finite_constants_rejected(self) -> None:
        """JSON NaN, Infinity, -Infinity are rejected during contract_from_json."""
        nan_json = '{"schema_version": 1, "contract_type": "Rect", "payload": {"x": NaN, "y": 0, "width": 10, "height": 10}}'
        inf_json = '{"schema_version": 1, "contract_type": "Rect", "payload": {"x": Infinity, "y": 0, "width": 10, "height": 10}}'
        neginf_json = '{"schema_version": 1, "contract_type": "Rect", "payload": {"x": -Infinity, "y": 0, "width": 10, "height": 10}}'
        for document in (nan_json, inf_json, neginf_json):
            with self.subTest(doc=document):
                with self.assertRaises((ValueError, json.JSONDecodeError)):
                    contract_from_json(document)

    def test_direct_dict_non_finite_floats_rejected(self) -> None:
        """Direct dict float('nan'), float('inf'), float('-inf') in confidence are rejected."""
        base_payload = {
            "schema_version": CONTRACT_SCHEMA_VERSION,
            "contract_type": "DetectedCard",
            "payload": {
                "code": "3S",
                "roi": {"x": 0, "y": 0, "width": 10, "height": 10},
                "zone": "my_hand",
                "confidence": 0.95,
                "seat": None,
            },
        }
        for bad_val in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(val=bad_val):
                envelope = json.loads(json.dumps(base_payload))
                envelope["payload"]["confidence"] = bad_val
                with self.assertRaises(ValueError):
                    contract_from_dict(envelope)

    def test_schema_version_boolean_rejected(self) -> None:
        """schema_version=True must raise TypeError."""
        envelope = {
            "schema_version": True,
            "contract_type": "Rect",
            "payload": {"x": 0, "y": 0, "width": 10, "height": 10},
        }
        with self.assertRaises(TypeError):
            contract_from_dict(envelope)

    def test_card_count_boolean_rejected(self) -> None:
        """player_card_counts value of True must raise TypeError."""
        ts_env = contract_to_dict(_sample_table_state())
        ts_env["payload"]["player_card_counts"]["0"] = True
        with self.assertRaises(TypeError):
            contract_from_dict(ts_env)

    def test_player_card_counts_seat_keys(self) -> None:
        """Seat keys like '00', unknown key, or non-str are rejected."""
        ts_env = contract_to_dict(_sample_table_state())
        # '00' key
        ts_env1 = json.loads(json.dumps(ts_env))
        ts_env1["payload"]["player_card_counts"] = {"00": 5}
        with self.assertRaises(ValueError):
            contract_from_dict(ts_env1)
        # unknown key '4'
        ts_env2 = json.loads(json.dumps(ts_env))
        ts_env2["payload"]["player_card_counts"] = {"4": 5}
        with self.assertRaises(ValueError):
            contract_from_dict(ts_env2)

    def test_button_id_invalid_types_rejected(self) -> None:
        """ButtonState.button_id of object/list/numeric/bool is rejected."""
        bs_env = contract_to_dict(_sample_button_state())
        for bad_id in ({"a": 1}, [1, 2], 123, True):
            with self.subTest(bad_id=bad_id):
                env = json.loads(json.dumps(bs_env)) if not isinstance(bad_id, (dict, list)) else dict(bs_env)
                env["payload"] = dict(env["payload"])
                env["payload"]["button_id"] = bad_id
                with self.assertRaises(TypeError):
                    contract_from_dict(env)

    def test_target_button_invalid_types_rejected(self) -> None:
        """ActionPlan.target_button of object/list/numeric/bool is rejected."""
        ap_env = contract_to_dict(_sample_action_plan_play())
        for bad_tb in ({"a": 1}, [1, 2], 123, True):
            with self.subTest(bad_tb=bad_tb):
                env = dict(ap_env)
                env["payload"] = dict(env["payload"])
                env["payload"]["target_button"] = bad_tb
                with self.assertRaises(TypeError):
                    contract_from_dict(env)

    def test_boolean_in_integer_fields_rejected(self) -> None:
        """Bool in frame_ts, Rect integer fields, timeout/retry, consensus counts is rejected."""
        rect_env = contract_to_dict(_sample_rect())
        rect_env["payload"]["x"] = True
        with self.assertRaises(TypeError):
            contract_from_dict(rect_env)

        ts_env = contract_to_dict(_sample_table_state())
        ts_env["payload"]["frame_ts"] = True
        with self.assertRaises(TypeError):
            contract_from_dict(ts_env)

        vs_env = contract_to_dict(_sample_verify_spec())
        vs_env["payload"]["timeout_ms"] = True
        with self.assertRaises(TypeError):
            contract_from_dict(vs_env)

        vs_env2 = contract_to_dict(_sample_verify_spec())
        vs_env2["payload"]["max_retries"] = True
        with self.assertRaises(TypeError):
            contract_from_dict(vs_env2)

        cs_env = contract_to_dict(_sample_consensus_spec())
        cs_env["payload"]["history_size"] = True
        with self.assertRaises(TypeError):
            contract_from_dict(cs_env)

    def test_wrong_container_types_rejected(self) -> None:
        """Wrong container types for cards, ROI, buttons, and player_card_counts raise TypeError."""
        ts_env = contract_to_dict(_sample_table_state())
        # cards as string
        env1 = dict(ts_env)
        env1["payload"] = dict(env1["payload"])
        env1["payload"]["my_cards"] = "3S,4S"
        with self.assertRaises(TypeError):
            contract_from_dict(env1)

        # ROI as list
        env2 = dict(ts_env)
        env2["payload"] = dict(env2["payload"])
        env2["payload"]["buttons"] = [{
            "button_id": "play", "label": "Play", "roi": [10, 20, 30, 40],
            "is_visible": True, "is_enabled": True, "confidence": 0.9
        }]
        with self.assertRaises(TypeError):
            contract_from_dict(env2)

        # buttons as string
        env3 = dict(ts_env)
        env3["payload"] = dict(env3["payload"])
        env3["payload"]["buttons"] = "play"
        with self.assertRaises(TypeError):
            contract_from_dict(env3)

        # player_card_counts as list
        env4 = dict(ts_env)
        env4["payload"] = dict(env4["payload"])
        env4["payload"]["player_card_counts"] = [10, 8]
        with self.assertRaises(TypeError):
            contract_from_dict(env4)


# -----------------------------------------------------------------------
# Adversarial Audit Tests (Strict Owner Audit PR #26)
# -----------------------------------------------------------------------


class AdversarialAuditTests(unittest.TestCase):
    """Regression tests required by Strict Owner Audit (PR #26)."""

    def test_duplicate_schema_version_json_key_rejected(self) -> None:
        """Duplicate schema_version key in JSON raises ValueError."""
        document = '{"schema_version": 99, "schema_version": 1, "contract_type": "Rect", "payload": {"x": 0, "y": 0, "width": 1, "height": 1}}'
        with self.assertRaises(ValueError) as cm:
            contract_from_json(document)
        self.assertIn("Duplicate", str(cm.exception))

    def test_duplicate_nested_counts_json_key_rejected(self) -> None:
        """Duplicate key in nested JSON player_card_counts raises ValueError."""
        document = (
            '{"schema_version": 1, "contract_type": "TableState", "payload": {'
            '"frame_id": "f1", "frame_ts": 100, "confidence": 0.9, "my_cards": [], "selected_cards": [], '
            '"last_played_combo": null, "player_card_counts": {"0": 3, "0": 12}, "turn_owner": null, '
            '"turn_owner_evidence": null, "buttons": [], "game_phase": "playing", "room_id": null}}'
        )
        with self.assertRaises(ValueError) as cm:
            contract_from_json(document)
        self.assertIn("Duplicate", str(cm.exception))

    def test_serialization_rejects_invalid_button_id_types(self) -> None:
        """contract_to_dict and contract_to_json reject dict/list/bool button_id and target_button."""
        for bad_id in ({"bad": 1}, [1, 2], True, 123):
            with self.subTest(bad_id=bad_id):
                bs = ButtonState(
                    button_id=bad_id,  # type: ignore
                    label="Bad",
                    roi=_sample_rect(),
                    is_visible=True,
                    is_enabled=True,
                    confidence=0.9,
                )
                with self.assertRaises(TypeError):
                    contract_to_dict(bs)
                with self.assertRaises(TypeError):
                    contract_to_json(bs)

                ap = ActionPlan(
                    kind=ActionKind.PLAY,
                    cards=("3S",),
                    target_button=bad_id,  # type: ignore
                    confidence=0.9,
                    reason="test",
                )
                with self.assertRaises(TypeError):
                    contract_to_dict(ap)
                with self.assertRaises(TypeError):
                    contract_to_json(ap)

    def test_serialization_rejects_non_finite_confidence(self) -> None:
        """contract_to_dict and contract_to_json reject contracts with non-finite confidence."""
        for bad_conf in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(conf=bad_conf):
                bs = ButtonState(
                    button_id=ButtonId.PLAY,
                    label="Play",
                    roi=_sample_rect(),
                    is_visible=True,
                    is_enabled=True,
                    confidence=0.9,
                )
                object.__setattr__(bs, "confidence", bad_conf)
                with self.assertRaises(ValueError):
                    contract_to_dict(bs)
                with self.assertRaises(ValueError):
                    contract_to_json(bs)

    def test_serialization_rejects_bool_in_integer_fields(self) -> None:
        """contract_to_dict and contract_to_json reject bool in integer fields like Rect.x and frame_ts."""
        r = Rect(x=True, y=0, width=10, height=10)  # type: ignore
        with self.assertRaises(TypeError):
            contract_to_dict(r)
        with self.assertRaises(TypeError):
            contract_to_json(r)

        ts = TableState(
            frame_id="f1",
            frame_ts=True,  # type: ignore
            confidence=0.9,
        )
        with self.assertRaises(TypeError):
            contract_to_dict(ts)
        with self.assertRaises(TypeError):
            contract_to_json(ts)

    def test_direct_dict_non_string_keys_rejected(self) -> None:
        """Envelope or payload dict with non-string key raises TypeError."""
        envelope = {
            123: "non-string key",
            "schema_version": 1,
            "contract_type": "Rect",
            "payload": {"x": 0, "y": 0, "width": 1, "height": 1},
        }
        with self.assertRaises(TypeError):
            contract_from_dict(envelope)  # type: ignore

        payload_env = {
            "schema_version": 1,
            "contract_type": "Rect",
            "payload": {123: 0, "y": 0, "width": 1, "height": 1},
        }
        with self.assertRaises(TypeError):
            contract_from_dict(payload_env)  # type: ignore

    def test_serialization_rejects_fake_enum_types(self) -> None:
        """contract_to_dict and contract_to_json reject fake Enum/IntEnum objects."""
        from enum import Enum, IntEnum

        class FakeZone(Enum):
            MY_HAND = "my_hand"
        class FakePhase(Enum):
            PLAYING = "playing"
        class FakeAction(Enum):
            WAIT = "wait"
        class FakeSeat(IntEnum):
            SELF = 0

        # FakeZone
        dc = _sample_detected_card()
        object.__setattr__(dc, "zone", FakeZone.MY_HAND)
        with self.assertRaises(TypeError):
            contract_to_dict(dc)

        # FakePhase
        ts = _sample_table_state()
        object.__setattr__(ts, "game_phase", FakePhase.PLAYING)
        with self.assertRaises(TypeError):
            contract_to_dict(ts)

        # FakeAction
        ap = _sample_action_plan_wait()
        object.__setattr__(ap, "kind", FakeAction.WAIT)
        with self.assertRaises(TypeError):
            contract_to_dict(ap)

        # FakeSeat in counts
        ts2 = _sample_table_state()
        object.__setattr__(ts2, "player_card_counts", {FakeSeat.SELF: 5})
        with self.assertRaises(TypeError):
            contract_to_dict(ts2)

    def test_serialization_rejects_duck_typed_objects(self) -> None:
        """contract_to_dict and contract_to_json reject duck-typed fake contracts."""
        class FakeRect:
            def __init__(self):
                self.x, self.y, self.width, self.height = 0, 0, 10, 10
        class FakeDetectedCard:
            def __init__(self):
                self.code = "3S"
                self.roi = _sample_rect()
                self.zone = CardZone.MY_HAND
                self.confidence = 0.9
                self.seat = None

        bs = _sample_button_state()
        object.__setattr__(bs, "roi", FakeRect())
        with self.assertRaises(TypeError):
            contract_to_dict(bs)

        ps = _sample_perception_snapshot()
        object.__setattr__(ps, "cards", (FakeDetectedCard(),))
        with self.assertRaises(TypeError):
            contract_to_dict(ps)

    def test_serialization_rejects_source_list_for_tuples(self) -> None:
        """contract_to_dict and contract_to_json reject list where tuple is required."""
        ps = _sample_perception_snapshot()
        object.__setattr__(ps, "cards", list(ps.cards))
        with self.assertRaises(TypeError):
            contract_to_dict(ps)

        ps2 = _sample_perception_snapshot()
        object.__setattr__(ps2, "buttons", list(ps2.buttons))
        with self.assertRaises(TypeError):
            contract_to_dict(ps2)

    def test_serialization_rejects_mutated_wrong_optional(self) -> None:
        """contract_to_dict and contract_to_json reject wrong type in optional fields."""
        # DetectedCard.seat is Optional[SeatPosition]
        dc = _sample_detected_card()
        object.__setattr__(dc, "seat", "self")  # not SeatPosition
        with self.assertRaises(TypeError):
            contract_to_dict(dc)

        # TableState.last_played_combo is Optional[CardCombo]
        ts = _sample_table_state()
        object.__setattr__(ts, "last_played_combo", "not a combo")
        with self.assertRaises(TypeError):
            contract_to_dict(ts)

    def test_serialization_rejects_duck_typed_mapping(self) -> None:
        """contract_to_dict and contract_to_json reject a fake mapping that only implements items()."""
        class FakeCounts:
            def items(self):
                return [(SeatPosition.SELF, 5)]
        ts = _sample_table_state()
        object.__setattr__(ts, "player_card_counts", FakeCounts())
        with self.assertRaises(TypeError):
            contract_to_dict(ts)
        with self.assertRaises(TypeError):
            contract_to_json(ts)

    def test_serialization_accepts_mapping_proxy_type(self) -> None:
        """contract_to_dict and contract_to_json accept types.MappingProxyType as a valid Mapping."""
        import types
        ts = _sample_table_state()
        object.__setattr__(ts, "player_card_counts", types.MappingProxyType({SeatPosition.SELF: 5}))
        d = contract_to_dict(ts)
        self.assertIn("0", d["payload"]["player_card_counts"])
        j = contract_to_json(ts)
        self.assertIn('"0":5', j.replace(" ", ""))

        # Round trip
        restored = contract_from_json(j)
        self.assertEqual(restored.player_card_counts, {SeatPosition.SELF: 5})


# -----------------------------------------------------------------------
# Consumer smoke tests
# -----------------------------------------------------------------------


class ConsumerSmokeTests(unittest.TestCase):
    """Verify serialization output is compatible with existing consumers.

    These tests use GameStateAdapter and replay table_state_to_dict/from_dict
    without modifying the consumer code.
    """

    def test_game_state_adapter_accepts_deserialized_table_state(self) -> None:
        """GameStateAdapter.adapt_state works on a round-tripped TableState."""
        from bot.agent.game_state_adapter import GameStateAdapter

        original = _sample_table_state()
        j = contract_to_json(original)
        restored = contract_from_json(j)
        adapter = GameStateAdapter()
        result = adapter.adapt_state(restored)
        self.assertEqual(result["my_hand"], list(original.my_cards))
        self.assertEqual(result["is_my_turn"], True)
        self.assertEqual(result["game_phase"], "playing")

    def test_replay_table_state_to_dict_matches_round_trip(self) -> None:
        """replay.table_state_to_dict can serialize a deserialized TableState."""
        from bot.replay.core import table_state_to_dict, table_state_from_dict

        original = _sample_table_state()
        j = contract_to_json(original)
        restored = contract_from_json(j)
        replay_dict = table_state_to_dict(restored)
        # The replay dict format uses seat names; verify it doesn't crash
        self.assertIn("my_cards", replay_dict)
        self.assertIn("buttons", replay_dict)
        # And round-trip through replay
        from_replay = table_state_from_dict(replay_dict)
        self.assertEqual(from_replay.my_cards, original.my_cards)
        self.assertEqual(from_replay.game_phase, original.game_phase)


# -----------------------------------------------------------------------
# Export from contracts package
# -----------------------------------------------------------------------


class PackageExportTests(unittest.TestCase):
    """Verify the serialization API is accessible from the contracts package."""

    def test_imports_from_contracts_package(self) -> None:
        import contracts
        self.assertEqual(contracts.CONTRACT_SCHEMA_VERSION, CONTRACT_SCHEMA_VERSION)
        self.assertTrue(callable(contracts.contract_to_dict))
        self.assertTrue(callable(contracts.contract_from_dict))
        self.assertTrue(callable(contracts.contract_to_json))
        self.assertTrue(callable(contracts.contract_from_json))


if __name__ == "__main__":
    unittest.main()
