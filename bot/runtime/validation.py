from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
import json
from typing import Any, Callable, Iterable, Mapping

from bot.runtime.schemas import BotBinding


@dataclass(frozen=True)
class ValidationResult:
    is_valid: bool
    reasons: tuple[str, ...] = ()


class SnapshotValidator:
    def validate(
        self,
        snapshot: Mapping[str, Any],
        *,
        binding: BotBinding | None = None,
    ) -> ValidationResult:
        reasons: list[str] = []

        card_regions = snapshot.get("card_regions", {})
        duplicates = self._find_duplicate_cards(card_regions.values())
        if duplicates:
            reasons.append(f"duplicate_cards={','.join(sorted(duplicates))}")

        cards_left = snapshot.get("cards_left_by_player", {})
        invalid_counts = [
            player_id
            for player_id, count in cards_left.items()
            if not isinstance(count, int) or count < 0 or count > 13
        ]
        if invalid_counts:
            reasons.append(f"invalid_card_counts={','.join(sorted(invalid_counts))}")

        if snapshot.get("state_transition_valid") is False:
            reasons.append("invalid_state_transition")

        if snapshot.get("anchor_ok") is False:
            reasons.append("anchor_mismatch")

        if binding and binding.identity_fingerprint:
            observed = snapshot.get("identity_fingerprint")
            if observed and observed != binding.identity_fingerprint:
                reasons.append("identity_fingerprint_mismatch")

        room_id = snapshot.get("room_id")
        if room_id is not None and not str(room_id).strip():
            reasons.append("empty_room_id")

        return ValidationResult(is_valid=not reasons, reasons=tuple(reasons))

    @staticmethod
    def _find_duplicate_cards(card_groups: Iterable[Iterable[str]]) -> set[str]:
        seen: set[str] = set()
        duplicates: set[str] = set()
        for group in card_groups:
            for card in group:
                if card in seen:
                    duplicates.add(card)
                else:
                    seen.add(card)
        return duplicates


@dataclass(frozen=True)
class ConsensusResult:
    is_stable: bool
    accepted_snapshot: Mapping[str, Any] | None
    observed_frames: int


class MultiFrameConsensus:
    def __init__(
        self,
        *,
        history_size: int = 3,
        required_matches: int = 2,
        key_builder: Callable[[Mapping[str, Any]], str] | None = None,
    ) -> None:
        if history_size < 1:
            raise ValueError("history_size must be positive.")
        if required_matches < 1 or required_matches > history_size:
            raise ValueError("required_matches must be within history_size.")

        self.history_size = history_size
        self.required_matches = required_matches
        self.key_builder = key_builder or self._default_key_builder
        self._history: dict[str, deque[tuple[str, Mapping[str, Any]]]] = defaultdict(
            lambda: deque(maxlen=history_size)
        )

    def observe(self, bot_id: str, snapshot: Mapping[str, Any]) -> ConsensusResult:
        key = self.key_builder(snapshot)
        history = self._history[bot_id]
        history.append((key, snapshot))

        matches = sum(1 for history_key, _ in history if history_key == key)
        is_stable = matches >= self.required_matches
        accepted_snapshot = snapshot if is_stable else None
        return ConsensusResult(
            is_stable=is_stable,
            accepted_snapshot=accepted_snapshot,
            observed_frames=len(history),
        )

    @staticmethod
    def _default_key_builder(snapshot: Mapping[str, Any]) -> str:
        canonical = json.dumps(snapshot, sort_keys=True, default=str)
        return canonical
