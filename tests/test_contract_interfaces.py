import unittest

from contracts.interfaces import (
    REGULAR_ACTION_CONSENSUS,
    TRANSITION_CONSENSUS,
    ActionKind,
    ActionPlan,
    GamePhase,
    Rect,
    SeatPosition,
    TableState,
    VerifyExpectedChange,
    VerifySpec,
    card_strength,
    sort_cards,
    validate_card_code,
)


class CardContractTests(unittest.TestCase):
    def test_validate_card_code_uses_rank_plus_suit_format(self) -> None:
        self.assertEqual(validate_card_code("10d"), "10D")
        self.assertEqual(validate_card_code("ah"), "AH")

    def test_sort_cards_uses_tien_len_rank_then_suit_order(self) -> None:
        cards = sort_cards(["2H", "3S", "3H", "AD", "AC"])
        self.assertEqual(cards, ("3S", "3H", "AC", "AD", "2H"))
        self.assertLess(card_strength("AH"), card_strength("2S"))

    def test_invalid_card_code_raises(self) -> None:
        with self.assertRaises(ValueError):
            validate_card_code("1Z")


class TableStateContractTests(unittest.TestCase):
    def test_table_state_sorts_cards_and_validates_counts(self) -> None:
        state = TableState(
            frame_id="frame-1",
            frame_ts=123,
            confidence=0.9,
            my_cards=("2H", "3S", "AH"),
            selected_cards=("AH", "3S"),
            player_card_counts={SeatPosition.SELF: 3, SeatPosition.LEFT: 5},
            game_phase=GamePhase.PLAYING,
        )

        self.assertEqual(state.my_cards, ("3S", "AH", "2H"))
        self.assertEqual(state.selected_cards, ("3S", "AH"))

    def test_invalid_player_card_count_raises(self) -> None:
        with self.assertRaises(ValueError):
            TableState(
                frame_id="frame-1",
                frame_ts=123,
                confidence=0.9,
                player_card_counts={SeatPosition.TOP: 14},
            )


class ActionPlanContractTests(unittest.TestCase):
    def test_play_action_requires_cards(self) -> None:
        with self.assertRaises(ValueError):
            ActionPlan(kind=ActionKind.PLAY)

    def test_verify_spec_and_consensus_defaults_match_decisions(self) -> None:
        verify = VerifySpec(
            roi=Rect(x=10, y=20, width=30, height=40),
            expected_change=VerifyExpectedChange.ROI_CHANGED,
            timeout_ms=1200,
            max_retries=2,
        )

        self.assertTrue(verify.escalate_to_hand_count)
        self.assertEqual(REGULAR_ACTION_CONSENSUS.history_size, 3)
        self.assertEqual(REGULAR_ACTION_CONSENSUS.required_matches, 2)
        self.assertTrue(REGULAR_ACTION_CONSENSUS.require_latest_frame)
        self.assertEqual(TRANSITION_CONSENSUS.history_size, 4)
        self.assertEqual(TRANSITION_CONSENSUS.required_matches, 3)


if __name__ == "__main__":
    unittest.main()
