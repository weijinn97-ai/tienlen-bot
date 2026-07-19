import random
import unittest

from bot.agent.local_agent import LocalAgent
from bot.rules import (
    ComboType,
    InvalidComboError,
    beats,
    classify_combo,
    enumerate_combos,
    enumerate_legal_moves,
    is_legal_play,
)
from contracts.interfaces import RANK_ORDER, SUIT_ORDER


class ComboClassificationTests(unittest.TestCase):
    def test_classifies_supported_combos(self) -> None:
        cases = {
            ("3S",): ComboType.SINGLE,
            ("4S", "4H"): ComboType.PAIR,
            ("5S", "5C", "5H"): ComboType.TRIPLE,
            ("6S", "6C", "6D", "6H"): ComboType.FOUR_OF_A_KIND,
            ("3S", "4C", "5D"): ComboType.STRAIGHT,
            ("3S", "3H", "4S", "4H", "5S", "5H"): ComboType.THREE_CONSECUTIVE_PAIRS,
            (
                "3S",
                "3H",
                "4S",
                "4H",
                "5S",
                "5H",
                "6S",
                "6H",
            ): ComboType.FOUR_CONSECUTIVE_PAIRS,
        }
        for cards, expected in cases.items():
            with self.subTest(cards=cards):
                self.assertEqual(classify_combo(cards).combo_type, expected)

    def test_rejects_duplicate_invalid_and_two_in_straight(self) -> None:
        for cards in (
            ("3S", "3S"),
            ("3S", "4S", "6S"),
            ("QS", "KH", "2D"),
            ("invalid",),
        ):
            with self.subTest(cards=cards), self.assertRaises(InvalidComboError):
                classify_combo(cards)


class ComboComparisonTests(unittest.TestCase):
    def test_same_type_uses_rank_suit_and_length(self) -> None:
        self.assertTrue(beats(("3H",), ("3D",)))
        self.assertTrue(beats(("4S", "4H"), ("4S", "4C")))
        self.assertTrue(beats(("4S", "5S", "6H"), ("3H", "4H", "5H")))
        self.assertFalse(beats(("4S", "5S", "6S", "7S"), ("3H", "4H", "5H")))

    def test_candidate_bomb_matrix(self) -> None:
        three_pairs = ("3S", "3H", "4S", "4H", "5S", "5H")
        four_kind = ("6S", "6C", "6D", "6H")
        four_pairs = ("7S", "7H", "8S", "8H", "9S", "9H", "10S", "10H")

        for target in (("2H",), ("2S", "2H")):
            self.assertTrue(beats(three_pairs, target))
            self.assertTrue(beats(four_kind, target))
            self.assertTrue(beats(four_pairs, target))

        self.assertTrue(beats(four_kind, three_pairs))
        self.assertTrue(beats(four_pairs, three_pairs))
        self.assertTrue(beats(four_pairs, four_kind))
        self.assertFalse(beats(four_kind, ("AS",)))


class LegalMoveEnumerationTests(unittest.TestCase):
    def test_enumeration_is_unique_and_every_combo_is_valid(self) -> None:
        hand = ("3S", "3H", "4S", "4H", "5S", "5H", "6D")
        combos = enumerate_combos(hand)
        card_sets = [combo.cards for combo in combos]

        self.assertEqual(len(card_sets), len(set(card_sets)))
        self.assertIn(("3S", "3H", "4S", "4H", "5S", "5H"), card_sets)
        self.assertTrue(all(is_legal_play(hand, cards) for cards in card_sets))

    def test_response_contains_only_combos_that_beat_target(self) -> None:
        hand = ("3S", "3H", "4S", "4H", "5S", "5H", "6D")
        legal = enumerate_legal_moves(hand, ("2H",))

        self.assertEqual(len(legal), 1)
        self.assertEqual(legal[0].combo_type, ComboType.THREE_CONSECUTIVE_PAIRS)
        self.assertTrue(beats(legal[0], ("2H",)))

    def test_first_game_opening_can_require_three_spades(self) -> None:
        hand = ("3S", "3H", "4S", "5S")
        legal = enumerate_legal_moves(hand, must_include_three_spades=True)

        self.assertTrue(legal)
        self.assertTrue(all("3S" in combo.cards for combo in legal))
        self.assertFalse(is_legal_play(hand, ("3H",), must_include_three_spades=True))


class LocalAgentRuleIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.agent = LocalAgent()

    def test_responds_to_pair_with_smallest_legal_pair(self) -> None:
        action = self.agent.decide_action(
            {
                "is_my_turn": True,
                "my_hand": ["4S", "4H", "5S", "5H", "9D"],
                "last_played_cards": ["3S", "3H"],
            }
        )
        self.assertEqual(action["action"], "play")
        self.assertEqual(action["cards"], ["4S", "4H"])

    def test_invalid_target_fails_safe(self) -> None:
        action = self.agent.decide_action(
            {
                "is_my_turn": True,
                "my_hand": ["4S", "4H"],
                "last_played_cards": ["3S", "4H"],
            }
        )
        self.assertEqual(action, {"action": "wait", "reason": "invalid_target_combo"})

    def test_missing_turn_confirmation_fails_safe(self) -> None:
        action = self.agent.decide_action({"my_hand": ["3S"], "last_played_cards": []})
        self.assertEqual(action, {"action": "wait", "reason": "not_my_turn"})

    def test_ten_thousand_generated_states_never_emit_invalid_play(self) -> None:
        rng = random.Random(20260719)
        deck = [f"{rank}{suit}" for rank in RANK_ORDER for suit in SUIT_ORDER]

        for _ in range(10_000):
            sample = rng.sample(deck, 6)
            hand, target = sample[:5], sample[5:]
            action = self.agent.decide_action(
                {
                    "is_my_turn": True,
                    "my_hand": hand,
                    "last_played_cards": target,
                }
            )
            self.assertIn(action["action"], {"play", "pass"})
            if action["action"] == "play":
                self.assertTrue(is_legal_play(hand, action["cards"], target))


if __name__ == "__main__":
    unittest.main()
