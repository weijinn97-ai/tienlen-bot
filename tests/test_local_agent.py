import unittest

from bot.agent.game_state_adapter import GameStateAdapter, normalize_agent_card
from bot.agent.local_agent import LocalAgent
from contracts.interfaces import CardCombo, GamePhase, SeatPosition, TableState


class GameStateAdapterTests(unittest.TestCase):
    def test_adapts_typed_table_state_to_agent_contract(self) -> None:
        state = TableState(
            frame_id="frame-1",
            frame_ts=123,
            confidence=0.9,
            my_cards=("2H", "3S"),
            last_played_combo=CardCombo(("10D",), owner=SeatPosition.LEFT),
            player_card_counts={seat: 13 for seat in SeatPosition},
            turn_owner=SeatPosition.SELF,
            game_phase=GamePhase.PLAYING,
        )
        adapted = GameStateAdapter().adapt_state(state)
        self.assertEqual(adapted["my_hand"], ["3S", "2H"])
        self.assertEqual(adapted["last_played_cards"], ["10D"])
        self.assertTrue(adapted["is_my_turn"])
        self.assertEqual(adapted["players_info"]["LEFT"]["cards_left"], 13)

    def test_legacy_card_values_are_normalized_at_boundary(self) -> None:
        self.assertEqual(normalize_agent_card("A_hearts"), "AH")
        adapted = GameStateAdapter().adapt_state(
            {"hand_cards": ["3_spades"], "last_played_combo": ["10_diamonds"]}
        )
        self.assertEqual(adapted["my_hand"], ["3S"])
        self.assertEqual(adapted["last_played_cards"], ["10D"])

    def test_already_adapted_legacy_state_keeps_explicit_turn_flag(self) -> None:
        adapted = GameStateAdapter().adapt_state(
            {"my_hand": ["3S"], "is_my_turn": True, "current_player_turn": "player-a"}
        )
        self.assertEqual(adapted["my_hand"], ["3S"])
        self.assertTrue(adapted["is_my_turn"])


class LocalAgentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.agent = LocalAgent()

    def test_waits_when_it_is_not_my_turn(self) -> None:
        action = self.agent.decide_action({"is_my_turn": False, "my_hand": ["3S"]})
        self.assertEqual(action["action"], "wait")

    def test_leads_with_smallest_normalized_card(self) -> None:
        action = self.agent.decide_action(
            {"is_my_turn": True, "my_hand": ["2H", "3H", "3S"], "last_played_cards": []}
        )
        self.assertEqual(action["cards"], ["3S"])

    def test_beats_single_using_tien_len_rank_and_suit_order(self) -> None:
        action = self.agent.decide_action(
            {
                "is_my_turn": True,
                "my_hand": ["4S", "3H", "4C"],
                "last_played_cards": ["3D"],
            }
        )
        self.assertEqual(action["cards"], ["3H"])


if __name__ == "__main__":
    unittest.main()
