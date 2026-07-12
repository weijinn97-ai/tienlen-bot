from __future__ import annotations

from typing import Any, Mapping

from contracts.interfaces import SeatPosition, TableState, validate_card_code


_LEGACY_SUITS = {
    "spades": "S",
    "clubs": "C",
    "diamonds": "D",
    "hearts": "H",
}


def normalize_agent_card(card: str) -> str:
    """Accept the contract encoding and temporarily support legacy rank_suit values."""

    candidate = card.strip()
    if "_" in candidate:
        rank, suit = candidate.rsplit("_", 1)
        normalized_suit = _LEGACY_SUITS.get(suit.lower())
        if normalized_suit is None:
            raise ValueError(f"Unknown legacy card suit: {suit!r}")
        candidate = f"{rank}{normalized_suit}"
    return validate_card_code(candidate)


class GameStateAdapter:
    """Adapt typed or legacy perception state for decision agents."""

    def adapt_state(self, raw_game_state: TableState | Mapping[str, Any]) -> dict[str, Any]:
        if isinstance(raw_game_state, TableState):
            combo = raw_game_state.last_played_combo
            return {
                "my_hand": list(raw_game_state.my_cards),
                "my_selected_cards": list(raw_game_state.selected_cards),
                "last_played_cards": list(combo.cards) if combo else [],
                "current_player_turn": (
                    raw_game_state.turn_owner.name if raw_game_state.turn_owner is not None else None
                ),
                "is_my_turn": raw_game_state.turn_owner == SeatPosition.SELF,
                "players_info": {
                    seat.name: {"cards_left": count}
                    for seat, count in raw_game_state.player_card_counts.items()
                },
                "num_players": len(raw_game_state.player_card_counts) or 4,
                "game_phase": raw_game_state.game_phase.value,
                "room_id": raw_game_state.room_id,
                "frame_id": raw_game_state.frame_id,
                "frame_ts": raw_game_state.frame_ts,
                "confidence": raw_game_state.confidence,
            }

        hand = raw_game_state.get(
            "my_cards",
            raw_game_state.get("hand_cards", raw_game_state.get("my_hand", [])),
        )
        selected = raw_game_state.get(
            "selected_cards",
            raw_game_state.get("my_selected_cards", []),
        )
        last_combo = raw_game_state.get(
            "last_played_combo",
            raw_game_state.get("last_played_cards", []),
        )
        last_combo = last_combo or []
        if isinstance(last_combo, Mapping):
            last_combo = last_combo.get("cards", [])
        turn_owner = raw_game_state.get(
            "turn_owner",
            raw_game_state.get(
                "current_turn_player",
                raw_game_state.get("current_player_turn"),
            ),
        )
        is_my_turn = raw_game_state.get("is_my_turn")
        if is_my_turn is None:
            is_my_turn = turn_owner in {
                SeatPosition.SELF,
                SeatPosition.SELF.name,
                SeatPosition.SELF.value,
                "self",
            }
        players_info = raw_game_state.get("players_info")
        if players_info is None:
            players_info = {
                str(seat): {"cards_left": count}
                for seat, count in raw_game_state.get("player_card_counts", {}).items()
            }
        return {
            "my_hand": [normalize_agent_card(card) for card in hand],
            "my_selected_cards": [normalize_agent_card(card) for card in selected],
            "last_played_cards": [normalize_agent_card(card) for card in last_combo],
            "current_player_turn": turn_owner,
            "is_my_turn": is_my_turn,
            "players_info": players_info,
            "num_players": raw_game_state.get("num_players", 4),
            "game_phase": raw_game_state.get("game_phase"),
            "room_id": raw_game_state.get("room_id"),
            "frame_id": raw_game_state.get("frame_id"),
            "frame_ts": raw_game_state.get("frame_ts"),
            "confidence": raw_game_state.get("confidence"),
        }
