"""Join perception, rules and action planning into one decision per frame.

Every part of this chain already existed - a card reader, a button detector, a
state assembler, a rules engine, a tap planner - but nothing connected them, so
the repository could read a frame and could plan a tap and could not get from one
to the other.

This is that join and nothing more. It decides; it does not tap. Execution stays
with ActionTapExecutor so a turn can be replayed against recorded frames without
an emulator attached, which is how the numbers in the module spec were measured.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Mapping

import numpy as np

from bot.actions.action_pipeline import ActionPlanBuilder
from bot.agent.game_state_adapter import GameStateAdapter
from bot.agent.local_agent import LocalAgent
from bot.perception.pipeline import PerceptionPipeline, PipelineFailure
from bot.perception.table_state import TableStateAssembler, TableStateConsensus
from bot.perception.turn_owner import YellowHighlightDetector
from bot.runtime.schemas import FrameEnvelope
from contracts.interfaces import (
    ActionKind,
    ActionPlan,
    ButtonId,
    ButtonState,
    GamePhase,
    PerceptionSnapshot,
    SeatPosition,
    TableState,
    TurnOwnerEvidence,
    TurnPrimarySignal,
    TransitionEvent,
)

ACTION_BUTTONS = (ButtonId.PLAY, ButtonId.PASS)


@dataclass(frozen=True)
class TurnOutcome:
    """What one frame produced, at every stage, including where it stopped."""

    snapshot: PerceptionSnapshot | None
    state: TableState | None
    decision: Mapping[str, Any]
    plan: ActionPlan | None
    failures: tuple[PipelineFailure, ...] = ()
    recovery: ButtonState | None = None

    @property
    def is_my_turn(self) -> bool:
        return self.state is not None and self.state.turn_owner is SeatPosition.SELF

    @property
    def acts(self) -> bool:
        return self.plan is not None and self.plan.kind is not ActionKind.WAIT


def _waiting(reason: str, **fields: Any) -> TurnOutcome:
    return TurnOutcome(
        snapshot=fields.get("snapshot"),
        state=fields.get("state"),
        decision={"action": ActionKind.WAIT.value, "reason": reason},
        plan=None,
        failures=fields.get("failures", ()),
    )


class TurnLoop:
    """Turn one frame into a decision, or into a documented reason not to act."""

    def __init__(
        self,
        pipeline: PerceptionPipeline,
        *,
        highlight: YellowHighlightDetector | None = None,
        assembler: TableStateAssembler | None = None,
        consensus: TableStateConsensus | None = None,
        adapter: GameStateAdapter | None = None,
        agent: LocalAgent | None = None,
        planner: ActionPlanBuilder | None = None,
    ) -> None:
        self.pipeline = pipeline
        self.highlight = highlight or YellowHighlightDetector()
        self.assembler = assembler or TableStateAssembler()
        self.consensus = consensus or TableStateConsensus()
        self.adapter = adapter or GameStateAdapter()
        self.agent = agent or LocalAgent()
        self.planner = planner or ActionPlanBuilder()

    def step(self, frame: FrameEnvelope, *, game_phase: GamePhase = GamePhase.PLAYING) -> TurnOutcome:
        result = self.pipeline.process(frame, game_phase=game_phase)
        if result.snapshot is None:
            return _waiting("frame_rejected", failures=result.failures)

        snapshot = self._with_turn_owner(result.snapshot, frame.image)
        state = self.assembler.build(snapshot)

        # While "Hủy tự động" is on screen the game is playing the hand itself,
        # so any decision made from this frame would be acted on by nobody. The
        # only useful move is to take the turn back, and it has to happen before
        # the clock runs out again.
        recovery = next(
            (
                button
                for button in snapshot.buttons
                if button.button_id is ButtonId.CANCEL_AUTO and button.is_visible
            ),
            None,
        )
        if recovery is not None:
            self.consensus.reset(snapshot.bot_id)
            return TurnOutcome(
                snapshot, state,
                {"action": ActionKind.WAIT.value, "reason": "auto_play_engaged"},
                None, result.failures, recovery,
            )

        if state.game_phase is not GamePhase.PLAYING:
            self.consensus.reset(snapshot.bot_id)
            return _waiting(
                "game_phase_not_playing",
                snapshot=snapshot,
                state=state,
                failures=result.failures,
            )

        if state.turn_owner is not SeatPosition.SELF:
            self.consensus.reset(snapshot.bot_id)
            return _waiting("not_my_turn", snapshot=snapshot, state=state, failures=result.failures)

        consensus = self.consensus.observe(
            snapshot.bot_id,
            state,
            transition=TransitionEvent.MY_TURN,
        )
        if not consensus.is_stable or consensus.accepted_state is None:
            reason = consensus.rejection_reason or (
                f"consensus_pending:{consensus.observed_frames}/"
                f"{consensus.required_matches}"
            )
            return _waiting(
                reason,
                snapshot=snapshot,
                state=state,
                failures=result.failures,
            )

        stable_state = consensus.accepted_state
        decision = self.agent.decide_action(self.adapter.adapt_state(stable_state))
        if decision.get("action") == ActionKind.WAIT.value:
            return TurnOutcome(snapshot, stable_state, decision, None, result.failures)

        try:
            plan = self.planner.build(dict(decision), snapshot)
        except ValueError as exc:
            # The planner refuses when a card it was told to play is not visible
            # or the button it needs is gone. Both mean the frame moved on, so
            # waiting for a fresh one is the only safe answer.
            return TurnOutcome(
                snapshot, state,
                {"action": ActionKind.WAIT.value, "reason": f"unplannable: {exc}"},
                None, result.failures,
            )
        return TurnOutcome(snapshot, stable_state, decision, plan, result.failures)

    def _with_turn_owner(
        self, snapshot: PerceptionSnapshot, image: np.ndarray
    ) -> PerceptionSnapshot:
        """Attach turn ownership. The action buttons decide; the ring may veto.

        The game shows "Đánh" or "Bỏ Lượt" only on the player's own turn, which
        makes them the strongest signal available. The gold avatar ring is a
        second witness, but it is not reliable enough to be required: measured
        over 582 frames an action button is visible on 165, and on 57 of those
        the ring is undecided. Requiring the ring would forfeit 35% of the bot's
        turns, and a forfeited turn is auto-played - the exact failure this loop
        exists to prevent.

        So the ring only vetoes, and only when it positively names another seat.
        That case occurred once in 582 frames; the veto costs one frame and
        guards against acting on a stale or transitional button.

        A ring on SELF with no action button is not our turn: that happens on 5
        frames, all without buttons, and acting there would act off-turn.
        """
        detection = self.highlight.detect(image)
        actionable = any(
            button.is_visible and button.button_id in ACTION_BUTTONS
            for button in snapshot.buttons
        )
        if actionable and detection.owner is not SeatPosition.SELF and detection.owner is not None:
            owner = detection.owner
        elif actionable:
            owner = SeatPosition.SELF
        else:
            owner = detection.owner if detection.owner is not SeatPosition.SELF else None

        evidence = None
        if owner is not None and detection.roi is not None:
            ring = detection.owner.name if detection.owner is not None else "none"
            evidence = TurnOwnerEvidence(
                primary_signal=TurnPrimarySignal.AVATAR_HIGHLIGHT,
                primary_roi=detection.roi,
                primary_confidence=detection.confidence,
                secondary_confidence=1.0 if actionable else 0.0,
                signals_agree=detection.owner is owner,
                notes=f"ring={ring};buttons={'yes' if actionable else 'no'}",
            )
        # Confidence is left as the pipeline computed it: the turn signals are a
        # gate on acting, not evidence about how well the cards were read.
        return replace(snapshot, turn_owner=owner, turn_owner_evidence=evidence)
