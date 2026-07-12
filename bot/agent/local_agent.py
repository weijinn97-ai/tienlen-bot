from __future__ import annotations

from typing import Any, Mapping

from configs.agent_config import LOCAL_AGENT_CONFIG
from contracts.interfaces import card_strength, validate_card_code


class LocalAgent:
    """Small deterministic fallback that currently supports single-card plays."""

    def __init__(self) -> None:
        self.model_path = LOCAL_AGENT_CONFIG["model_path"]
        self.rules_config = LOCAL_AGENT_CONFIG["rules_config"]

    def decide_action(self, game_state: Mapping[str, Any]) -> dict[str, Any]:
        if game_state.get("is_my_turn") is False:
            return {"action": "wait", "reason": "not_my_turn"}

        cards_in_hand = [validate_card_code(card) for card in game_state.get("my_hand", [])]
        last_played_cards = [
            validate_card_code(card) for card in game_state.get("last_played_cards", [])
        ]
        if not cards_in_hand:
            return {"action": "pass", "reason": "empty_or_unreadable_hand"}

        sorted_hand = sorted(cards_in_hand, key=card_strength)
        if not last_played_cards:
            return {
                "action": "play",
                "cards": [sorted_hand[0]],
                "reason": "lead_smallest_single",
            }

        if len(last_played_cards) == 1:
            target_strength = card_strength(last_played_cards[0])
            playable = [card for card in sorted_hand if card_strength(card) > target_strength]
            if playable:
                return {
                    "action": "play",
                    "cards": [playable[0]],
                    "reason": "beat_single_with_smallest_card",
                }

        return {"action": "pass", "reason": "no_supported_play"}

    def _card_value(self, card_str: str) -> int:
        rank_strength, suit_strength = card_strength(card_str)
        return rank_strength * 4 + suit_strength
