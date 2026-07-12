from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from bot.agent.decision_orchestrator import DecisionOrchestrator
from bot.capture.capture_worker import CaptureWorker
from bot.inference.inference_service import InferenceResult, InferenceService
from bot.perception.table_state import TableStateAssembler, TableStateConsensus
from bot.runtime.schemas import BotBinding, CaptureMode, FrameEnvelope
from bot.runtime.validation import MultiFrameConsensus, SnapshotValidator
from bot.stability.watchdog import CircuitBreaker
from contracts.interfaces import PerceptionSnapshot, TableState, TransitionEvent


@dataclass
class BotWorkerState:
    game_state: dict[str, Any] | TableState | None = None
    decision_state: dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0
    last_frame: FrameEnvelope | None = None
    last_snapshot: Mapping[str, Any] | None = None
    last_perception_snapshot: PerceptionSnapshot | None = None
    paused: bool = False


class BotWorker:
    def __init__(
        self,
        binding: BotBinding,
        *,
        capture_worker: CaptureWorker | None = None,
        inference_service: InferenceService | None = None,
        decision_orchestrator: DecisionOrchestrator | None = None,
        snapshot_validator: SnapshotValidator | None = None,
        consensus: MultiFrameConsensus | None = None,
        table_state_assembler: TableStateAssembler | None = None,
        table_state_consensus: TableStateConsensus | None = None,
        circuit_breaker: CircuitBreaker | None = None,
    ) -> None:
        self.binding = binding
        self.capture_worker = capture_worker or CaptureWorker(binding)
        self.inference_service = inference_service
        self.decision_orchestrator = decision_orchestrator or DecisionOrchestrator()
        self.snapshot_validator = snapshot_validator or SnapshotValidator()
        self.consensus = consensus or MultiFrameConsensus()
        self.table_state_assembler = table_state_assembler or TableStateAssembler()
        self.table_state_consensus = table_state_consensus or TableStateConsensus()
        self.circuit_breaker = circuit_breaker or CircuitBreaker()
        self.state = BotWorkerState()

    def set_capture_mode(self, *, is_my_turn: bool, just_acted: bool = False) -> None:
        if is_my_turn or just_acted:
            self.capture_worker.set_mode(CaptureMode.ACTIVE)
        elif self.state.game_state:
            self.capture_worker.set_mode(CaptureMode.TRACKING)
        else:
            self.capture_worker.set_mode(CaptureMode.IDLE)

    def capture_frame(self) -> FrameEnvelope:
        frame = self.capture_worker.capture_once()
        self.state.last_frame = frame
        return frame

    def submit_for_inference(self, frame: FrameEnvelope) -> InferenceResult | None:
        if self.inference_service is None:
            return None
        future = self.inference_service.submit(
            frame,
            metadata={
                "bot_id": self.binding.bot_id,
                "frame_id": frame.frame_id,
            },
        )
        return future.result()

    def process_snapshot(self, snapshot: Mapping[str, Any]) -> dict[str, Any] | None:
        if self.circuit_breaker.state.is_open:
            self.state.paused = True
            return None

        validation = self.snapshot_validator.validate(snapshot, binding=self.binding)
        if not validation.is_valid:
            self.state.retry_count += 1
            self.circuit_breaker.record_failure(",".join(validation.reasons))
            return None

        consensus = self.consensus.observe(self.binding.bot_id, snapshot)
        if not consensus.is_stable or consensus.accepted_snapshot is None:
            return None

        stable_snapshot = consensus.accepted_snapshot
        action = self.decision_orchestrator.decide_action(dict(stable_snapshot))
        self.state.game_state = dict(stable_snapshot)
        self.state.decision_state = action
        self.state.last_snapshot = stable_snapshot
        self.state.retry_count = 0
        self.state.paused = False
        self.circuit_breaker.record_success()
        return action

    def process_perception_snapshot(
        self,
        snapshot: PerceptionSnapshot,
        *,
        transition: TransitionEvent | None = None,
    ) -> dict[str, Any] | None:
        """Process the typed perception path without removing legacy snapshot support."""

        if self.circuit_breaker.state.is_open:
            self.state.paused = True
            return None
        if snapshot.bot_id != self.binding.bot_id:
            self.state.retry_count += 1
            self.circuit_breaker.record_failure("perception_bot_id_mismatch")
            return None

        table_state = self.table_state_assembler.build(snapshot)
        consensus = self.table_state_consensus.observe(
            self.binding.bot_id,
            table_state,
            transition=transition,
        )
        if consensus.rejection_reason is not None:
            self.state.retry_count += 1
            self.circuit_breaker.record_failure(consensus.rejection_reason)
            return None
        if not consensus.is_stable or consensus.accepted_state is None:
            return None

        stable_state = consensus.accepted_state
        action = self.decision_orchestrator.decide_action(stable_state)
        self.state.game_state = stable_state
        self.state.decision_state = action
        self.state.last_perception_snapshot = snapshot
        self.state.retry_count = 0
        self.state.paused = False
        self.circuit_breaker.record_success()
        return action
