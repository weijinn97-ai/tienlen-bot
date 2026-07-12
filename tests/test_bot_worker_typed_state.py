import time
import unittest

from bot.perception.table_state import TableStateConsensus
from bot.runtime.bot_worker import BotWorker
from bot.runtime.schemas import BotBinding
from contracts.interfaces import GamePhase, PerceptionSnapshot, SeatPosition, TableState


class StubCaptureWorker:
    def set_mode(self, mode) -> None:
        self.mode = mode


class StubDecisionOrchestrator:
    def __init__(self) -> None:
        self.seen_state = None

    def decide_action(self, state: TableState) -> dict:
        self.seen_state = state
        return {"action": "wait"}


class TypedBotWorkerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now_ns = time.monotonic_ns()
        self.decision = StubDecisionOrchestrator()
        self.worker = BotWorker(
            BotBinding(
                bot_id="bot-1",
                hwnd=100,
                adb_serial="127.0.0.1:7555",
                pid=200,
            ),
            capture_worker=StubCaptureWorker(),
            decision_orchestrator=self.decision,
            table_state_consensus=TableStateConsensus(clock_ns=lambda: self.now_ns),
        )

    def snapshot(self, frame_id: str, *, bot_id: str = "bot-1") -> PerceptionSnapshot:
        return PerceptionSnapshot(
            bot_id=bot_id,
            frame_id=frame_id,
            frame_ts=self.now_ns,
            confidence=0.9,
            player_card_counts={seat: 13 for seat in SeatPosition},
            turn_owner=SeatPosition.SELF,
            game_phase=GamePhase.PLAYING,
        )

    def test_decides_only_after_typed_state_reaches_consensus(self) -> None:
        first = self.worker.process_perception_snapshot(self.snapshot("frame-1"))
        second = self.worker.process_perception_snapshot(self.snapshot("frame-2"))
        self.assertIsNone(first)
        self.assertEqual(second, {"action": "wait"})
        self.assertIsInstance(self.worker.state.game_state, TableState)
        self.assertEqual(self.decision.seen_state.frame_id, "frame-2")

    def test_rejects_snapshot_for_a_different_bot(self) -> None:
        action = self.worker.process_perception_snapshot(
            self.snapshot("frame-1", bot_id="bot-2")
        )
        self.assertIsNone(action)
        self.assertEqual(self.worker.state.retry_count, 1)
        self.assertEqual(
            self.worker.circuit_breaker.state.last_error,
            "perception_bot_id_mismatch",
        )


if __name__ == "__main__":
    unittest.main()
