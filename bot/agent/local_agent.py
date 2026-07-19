from __future__ import annotations

from typing import Any, Mapping

from bot.rules import InvalidComboError, classify_combo, enumerate_legal_moves, is_legal_play
from configs.agent_config import LOCAL_AGENT_CONFIG
from contracts.interfaces import card_strength, validate_card_code


class LocalAgent:
    """Deterministic fallback that emits only plays accepted by the rules engine."""

    def __init__(self) -> None:
        self.model_path = LOCAL_AGENT_CONFIG["model_path"]
        self.rules_config = LOCAL_AGENT_CONFIG["rules_config"]

    def decide_action(self, game_state: Mapping[str, Any]) -> dict[str, Any]:
        if game_state.get("is_my_turn") is not True:
            return {"action": "wait", "reason": "not_my_turn"}

        try:
            cards_in_hand = [
                validate_card_code(card) for card in game_state.get("my_hand", [])
            ]
            last_played_cards = [
                validate_card_code(card)
                for card in game_state.get("last_played_cards", [])
            ]
        except ValueError:
            return {"action": "wait", "reason": "invalid_card_state"}

        if not cards_in_hand:
            return {"action": "wait", "reason": "empty_or_unreadable_hand"}

        try:
            target = classify_combo(last_played_cards) if last_played_cards else None
            legal_moves = enumerate_legal_moves(cards_in_hand, target)
        except (InvalidComboError, ValueError):
            return {"action": "wait", "reason": "invalid_target_combo"}

        if not legal_moves:
            return {"action": "pass", "reason": "no_legal_response"}

        selected = legal_moves[0]
        if not is_legal_play(cards_in_hand, selected.cards, target):
            return {"action": "wait", "reason": "rules_invariant_failed"}

        prefix = "lead" if target is None else "respond"
        return {
            "action": "play",
            "cards": list(selected.cards),
            "reason": f"{prefix}_{selected.combo_type.value}",
        }

    def _card_value(self, card_str: str) -> int:
        rank_strength, suit_strength = card_strength(card_str)
        return rank_strength * 4 + suit_strength
