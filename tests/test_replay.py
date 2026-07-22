import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from bot.agent.local_agent import LocalAgent
from bot.replay import (
    EventKind,
    ReplayMismatchError,
    ReplayRecorder,
    ReplayValidationError,
    document_to_bundle,
    read_bundle,
    reproduce_decisions,
    table_state_from_dict,
    table_state_to_dict,
)
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


def canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode()


def make_state() -> TableState:
    return TableState(
        frame_id="frame-1",
        frame_ts=123456,
        confidence=0.98,
        my_cards=("3S", "4C", "5D"),
        selected_cards=("3S",),
        last_played_combo=CardCombo(("3H",), "single", SeatPosition.LEFT, 0.97),
        player_card_counts={seat: 10 + int(seat) for seat in SeatPosition},
        turn_owner=SeatPosition.SELF,
        turn_owner_evidence=TurnOwnerEvidence(
            primary_signal=TurnPrimarySignal.AVATAR_HIGHLIGHT,
            primary_roi=Rect(1, 2, 30, 40),
            primary_confidence=0.99,
            secondary_confidence=0.9,
            signals_agree=True,
            notes="agreed",
        ),
        buttons=(ButtonState(ButtonId.PLAY, "Play", Rect(5, 6, 70, 20), True, True, 0.96),),
        game_phase=GamePhase.PLAYING,
        room_id="private-room",
    )


class ReplayTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary.name) / "fixture.json"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_table_state_contract_round_trip(self) -> None:
        state = make_state()
        restored = table_state_from_dict(table_state_to_dict(state))
        self.assertEqual(restored, state)

    def test_bundle_round_trip_and_hash_chain(self) -> None:
        recorder = ReplayRecorder("bot-1", "session-1")
        recorder.append(EventKind.FRAME, frame_ts=1, payload={"frame_id": "one"})
        recorder.append(EventKind.VERIFICATION, frame_ts=2, payload={"passed": True})
        recorder.write(self.path)
        bundle = read_bundle(self.path)
        self.assertEqual(len(bundle.events), 2)
        self.assertEqual(bundle.events[1].previous_hash, bundle.events[0].event_hash)

    def test_sensitive_values_are_redacted_recursively(self) -> None:
        recorder = ReplayRecorder("bot-1", "session-1")
        event = recorder.append(
            EventKind.PERCEPTION,
            frame_ts=1,
            payload={"token": "abc", "nested": {"adb_serial": "127.0.0.1:1"}},
        )
        self.assertEqual(event.payload["token"], "[REDACTED]")
        self.assertEqual(event.payload["nested"]["adb_serial"], "[REDACTED]")

    def test_raw_frame_and_binary_payload_are_rejected(self) -> None:
        recorder = ReplayRecorder("bot-1", "session-1")
        with self.assertRaisesRegex(ReplayValidationError, "raw_frame_forbidden"):
            recorder.append(EventKind.FRAME, frame_ts=1, payload={"raw_frame": "data"})
        with self.assertRaisesRegex(ReplayValidationError, "binary_payload_forbidden"):
            recorder.append(EventKind.FRAME, frame_ts=1, payload={"value": b"bytes"})

    def test_reader_rejects_unredacted_sensitive_payload(self) -> None:
        recorder = ReplayRecorder("bot-1", "session-1")
        recorder.append(EventKind.FRAME, frame_ts=1, payload={"value": "safe"})
        recorder.write(self.path)
        document = json.loads(self.path.read_text())
        event = document["events"][0]
        event["payload"] = {"token": "secret"}
        material = {key: value for key, value in event.items() if key != "event_hash"}
        event["event_hash"] = hashlib.sha256(canonical(material)).hexdigest()
        body = {key: value for key, value in document.items() if key != "bundle_checksum"}
        document["bundle_checksum"] = hashlib.sha256(canonical(body)).hexdigest()
        with self.assertRaisesRegex(ReplayValidationError, "unredacted_sensitive_value"):
            document_to_bundle(document)

    def test_bundle_checksum_detects_mutation(self) -> None:
        recorder = ReplayRecorder("bot-1", "session-1")
        recorder.append(EventKind.FRAME, frame_ts=1, payload={"frame_id": "one"})
        recorder.write(self.path)
        document = json.loads(self.path.read_text())
        document["events"][0]["payload"]["frame_id"] = "changed"
        self.path.write_text(json.dumps(document), encoding="utf-8")
        with self.assertRaisesRegex(ReplayValidationError, "bundle_checksum_mismatch"):
            read_bundle(self.path)

    def test_event_hash_detects_mutation_even_with_new_bundle_checksum(self) -> None:
        recorder = ReplayRecorder("bot-1", "session-1")
        recorder.append(EventKind.FRAME, frame_ts=1, payload={"frame_id": "one"})
        recorder.write(self.path)
        document = json.loads(self.path.read_text())
        document["events"][0]["payload"]["frame_id"] = "changed"
        body = {key: value for key, value in document.items() if key != "bundle_checksum"}
        document["bundle_checksum"] = hashlib.sha256(canonical(body)).hexdigest()
        self.path.write_text(json.dumps(document), encoding="utf-8")
        with self.assertRaisesRegex(ReplayValidationError, "event_hash_mismatch"):
            read_bundle(self.path)

    def test_incomplete_record_fails_with_explicit_reason(self) -> None:
        self.path.write_text('{"schema_version": 1}', encoding="utf-8")
        with self.assertRaisesRegex(ReplayValidationError, "invalid_document_fields"):
            read_bundle(self.path)

    def test_deterministic_recorders_write_identical_bytes(self) -> None:
        first = ReplayRecorder("bot-1", "session-1")
        second = ReplayRecorder("bot-1", "session-1")
        for recorder in (first, second):
            recorder.append(EventKind.FRAME, frame_ts=1, payload={"b": 2, "a": 1})
        second_path = self.path.with_name("second.json")
        first.write(self.path)
        second.write(second_path)
        self.assertEqual(self.path.read_bytes(), second_path.read_bytes())

    def test_offline_replay_reproduces_local_decision(self) -> None:
        decision_input = {
            "is_my_turn": True,
            "my_hand": ["3S", "4C", "5D"],
            "last_played_cards": ["3H"],
        }
        agent = LocalAgent()
        expected = agent.decide_action(decision_input)
        recorder = ReplayRecorder("bot-1", "session-1")
        recorder.append_table_state(make_state(), decision_input=decision_input)
        recorder.append(EventKind.DECISION, frame_ts=123457, payload={"result": expected})
        self.assertEqual(reproduce_decisions(recorder.bundle(), agent.decide_action), 1)

    def test_decision_mismatch_is_not_silently_accepted(self) -> None:
        recorder = ReplayRecorder("bot-1", "session-1")
        recorder.append_table_state(make_state(), decision_input={"is_my_turn": False})
        recorder.append(
            EventKind.DECISION,
            frame_ts=123457,
            payload={"result": {"action": "play", "cards": ["3S"]}},
        )
        with self.assertRaisesRegex(ReplayMismatchError, "decision_mismatch"):
            reproduce_decisions(recorder.bundle(), LocalAgent().decide_action)

    def test_oversized_replay_is_rejected(self) -> None:
        self.path.write_bytes(b"x" * 20)
        with self.assertRaisesRegex(ReplayValidationError, "replay_too_large"):
            read_bundle(self.path, max_bytes=10)


if __name__ == "__main__":
    unittest.main()
