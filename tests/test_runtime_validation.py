import unittest

from bot.runtime.schemas import BotBinding
from bot.runtime.validation import MultiFrameConsensus, SnapshotValidator


class SnapshotValidatorTests(unittest.TestCase):
    def test_duplicate_cards_are_rejected(self) -> None:
        binding = BotBinding(
            bot_id="bot-1",
            hwnd=100,
            adb_serial="127.0.0.1:7555",
            pid=200,
            identity_fingerprint="room-a",
        )
        snapshot = {
            "card_regions": {
                "my_hand": ["3_spades", "4_hearts"],
                "table": ["4_hearts"],
            },
            "identity_fingerprint": "room-a",
        }

        result = SnapshotValidator().validate(snapshot, binding=binding)

        self.assertFalse(result.is_valid)
        self.assertIn("duplicate_cards=4_hearts", result.reasons)

    def test_identity_mismatch_is_rejected(self) -> None:
        binding = BotBinding(
            bot_id="bot-1",
            hwnd=100,
            adb_serial="127.0.0.1:7555",
            pid=200,
            identity_fingerprint="room-a",
        )

        result = SnapshotValidator().validate(
            {"identity_fingerprint": "room-b"},
            binding=binding,
        )

        self.assertFalse(result.is_valid)
        self.assertIn("identity_fingerprint_mismatch", result.reasons)


class ConsensusTests(unittest.TestCase):
    def test_consensus_requires_repeated_snapshot(self) -> None:
        consensus = MultiFrameConsensus(history_size=3, required_matches=2)

        first = consensus.observe("bot-1", {"turn": "player-a"})
        second = consensus.observe("bot-1", {"turn": "player-a"})

        self.assertFalse(first.is_stable)
        self.assertTrue(second.is_stable)
        self.assertEqual(second.accepted_snapshot, {"turn": "player-a"})


if __name__ == "__main__":
    unittest.main()
