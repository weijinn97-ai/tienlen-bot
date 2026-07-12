from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
import json
import time
from typing import Callable

from contracts.interfaces import (
    REGULAR_ACTION_CONSENSUS,
    TRANSITION_CONSENSUS,
    CardCombo,
    CardZone,
    ConsensusSpec,
    PerceptionSnapshot,
    TableState,
    TransitionEvent,
)


class TableStateAssembler:
    """Convert typed perception output into the decision-facing table state."""

    def build(self, snapshot: PerceptionSnapshot) -> TableState:
        my_cards = tuple(
            card.code for card in snapshot.cards if card.zone == CardZone.MY_HAND
        )
        selected_cards = tuple(
            card.code for card in snapshot.cards if card.zone == CardZone.SELECTED
        )
        table_cards = tuple(card for card in snapshot.cards if card.zone == CardZone.TABLE)
        last_played_combo = self._build_table_combo(table_cards)

        return TableState(
            frame_id=snapshot.frame_id,
            frame_ts=snapshot.frame_ts,
            confidence=snapshot.confidence,
            my_cards=my_cards,
            selected_cards=selected_cards,
            last_played_combo=last_played_combo,
            player_card_counts=dict(snapshot.player_card_counts),
            turn_owner=snapshot.turn_owner,
            turn_owner_evidence=snapshot.turn_owner_evidence,
            buttons=snapshot.buttons,
            game_phase=snapshot.game_phase,
            room_id=snapshot.room_id,
        )

    @staticmethod
    def _build_table_combo(table_cards: tuple) -> CardCombo | None:
        if not table_cards:
            return None
        owners = {card.seat for card in table_cards if card.seat is not None}
        owner = next(iter(owners)) if len(owners) == 1 else None
        confidence = min(card.confidence for card in table_cards)
        return CardCombo(
            cards=tuple(card.code for card in table_cards),
            owner=owner,
            confidence=confidence,
        )


@dataclass(frozen=True)
class StateAcceptancePolicy:
    min_confidence: float = 0.65
    max_age_ns: int = 2_000_000_000

    def __post_init__(self) -> None:
        if not 0.0 <= self.min_confidence <= 1.0:
            raise ValueError("min_confidence must be within [0.0, 1.0].")
        if self.max_age_ns <= 0:
            raise ValueError("max_age_ns must be positive.")

    def rejection_reason(self, state: TableState, *, now_ns: int) -> str | None:
        if state.confidence < self.min_confidence:
            return "confidence_below_threshold"
        if state.frame_ts > now_ns:
            return "frame_timestamp_in_future"
        if now_ns - state.frame_ts > self.max_age_ns:
            return "frame_too_old"
        return None


@dataclass(frozen=True)
class TableStateConsensusResult:
    is_stable: bool
    accepted_state: TableState | None
    observed_frames: int
    required_matches: int
    rejection_reason: str | None = None


class TableStateConsensus:
    """Apply regular or transition consensus while always including the latest frame."""

    def __init__(
        self,
        *,
        policy: StateAcceptancePolicy | None = None,
        regular_spec: ConsensusSpec = REGULAR_ACTION_CONSENSUS,
        transition_spec: ConsensusSpec = TRANSITION_CONSENSUS,
        clock_ns: Callable[[], int] = time.monotonic_ns,
    ) -> None:
        self.policy = policy or StateAcceptancePolicy()
        self.regular_spec = regular_spec
        self.transition_spec = transition_spec
        self.clock_ns = clock_ns
        history_size = max(regular_spec.history_size, transition_spec.history_size)
        self._history: dict[str, deque[tuple[str, TableState]]] = defaultdict(
            lambda: deque(maxlen=history_size)
        )

    def observe(
        self,
        bot_id: str,
        state: TableState,
        *,
        transition: TransitionEvent | None = None,
    ) -> TableStateConsensusResult:
        if not bot_id.strip():
            raise ValueError("bot_id must not be empty.")
        spec = self.transition_spec if transition is not None else self.regular_spec
        rejection_reason = self.policy.rejection_reason(state, now_ns=self.clock_ns())
        if rejection_reason is not None:
            return TableStateConsensusResult(
                is_stable=False,
                accepted_state=None,
                observed_frames=len(self._history[bot_id]),
                required_matches=spec.required_matches,
                rejection_reason=rejection_reason,
            )

        key = self._semantic_key(state)
        history = self._history[bot_id]
        history.append((key, state))
        active_window = list(history)[-spec.history_size :]
        matches = sum(history_key == key for history_key, _ in active_window)
        is_stable = matches >= spec.required_matches
        return TableStateConsensusResult(
            is_stable=is_stable,
            accepted_state=state if is_stable else None,
            observed_frames=len(active_window),
            required_matches=spec.required_matches,
        )

    @staticmethod
    def _semantic_key(state: TableState) -> str:
        combo = state.last_played_combo
        payload = {
            "my_cards": state.my_cards,
            "selected_cards": state.selected_cards,
            "last_played_combo": combo.cards if combo else (),
            "last_played_owner": combo.owner if combo else None,
            "player_card_counts": sorted(
                (int(seat), count) for seat, count in state.player_card_counts.items()
            ),
            "turn_owner": state.turn_owner,
            "buttons": sorted(
                (
                    str(button.button_id),
                    button.is_visible,
                    button.is_enabled,
                )
                for button in state.buttons
            ),
            "game_phase": state.game_phase,
            "room_id": state.room_id,
        }
        return json.dumps(payload, sort_keys=True, default=str)
