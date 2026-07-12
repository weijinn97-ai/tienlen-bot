import unittest

from bot.perception.table_state import (
    StateAcceptancePolicy,
    TableStateAssembler,
    TableStateConsensus,
)
from contracts.interfaces import (
    CardZone,
    DetectedCard,
    GamePhase,
    PerceptionSnapshot,
    Rect,
    SeatPosition,
    TableState,
    TransitionEvent,
)


NOW_NS = 10_000_000_000


def make_state(
    frame_id: str,
    *,
    turn_owner: SeatPosition = SeatPosition.SELF,
    confidence: float = 0.9,
    frame_ts: int = NOW_NS,
) -> TableState:
    return TableState(
        frame_id=frame_id,
        frame_ts=frame_ts,
        confidence=confidence,
        my_cards=("3S", "AH"),
        player_card_counts={seat: 13 for seat in SeatPosition},
        turn_owner=turn_owner,
        game_phase=GamePhase.PLAYING,
    )


class TableStateAssemblerTests(unittest.TestCase):
    def test_builds_decision_state_from_perception_snapshot(self) -> None:
        roi = Rect(10, 20, 30, 40)
        snapshot = PerceptionSnapshot(
            bot_id="bot-1",
            frame_id="frame-1",
            frame_ts=NOW_NS,
            confidence=0.92,
            cards=(
                DetectedCard("AH", roi, CardZone.MY_HAND, 0.98),
                DetectedCard("3S", roi, CardZone.MY_HAND, 0.97),
                DetectedCard("4D", roi, CardZone.SELECTED, 0.96),
                DetectedCard("10H", roi, CardZone.TABLE, 0.91, SeatPosition.LEFT),
            ),
            player_card_counts={seat: 13 for seat in SeatPosition},
            turn_owner=SeatPosition.TOP,
            game_phase=GamePhase.PLAYING,
            room_id="room-1",
        )

        state = TableStateAssembler().build(snapshot)

        self.assertEqual(state.my_cards, ("3S", "AH"))
        self.assertEqual(state.selected_cards, ("4D",))
        self.assertEqual(state.last_played_combo.cards, ("10H",))
        self.assertEqual(state.last_played_combo.owner, SeatPosition.LEFT)
        self.assertEqual(state.turn_owner, SeatPosition.TOP)
        self.assertEqual(state.room_id, "room-1")


class TableStateConsensusTests(unittest.TestCase):
    def make_consensus(self) -> TableStateConsensus:
        return TableStateConsensus(clock_ns=lambda: NOW_NS)

    def test_regular_state_uses_two_of_three_consensus(self) -> None:
        consensus = self.make_consensus()
        first = consensus.observe("bot-1", make_state("frame-1"))
        second = consensus.observe("bot-1", make_state("frame-2"))
        self.assertFalse(first.is_stable)
        self.assertTrue(second.is_stable)
        self.assertEqual(second.required_matches, 2)
        self.assertEqual(second.accepted_state.frame_id, "frame-2")

    def test_latest_frame_must_belong_to_consensus_group(self) -> None:
        consensus = self.make_consensus()
        consensus.observe("bot-1", make_state("frame-1", turn_owner=SeatPosition.SELF))
        consensus.observe("bot-1", make_state("frame-2", turn_owner=SeatPosition.SELF))
        result = consensus.observe("bot-1", make_state("frame-3", turn_owner=SeatPosition.LEFT))
        self.assertFalse(result.is_stable)
        self.assertIsNone(result.accepted_state)

    def test_transition_state_uses_three_of_four_consensus(self) -> None:
        consensus = self.make_consensus()
        results = [
            consensus.observe(
                "bot-1",
                make_state(f"frame-{index}"),
                transition=TransitionEvent.MY_TURN,
            )
            for index in range(1, 4)
        ]
        self.assertFalse(results[1].is_stable)
        self.assertTrue(results[2].is_stable)
        self.assertEqual(results[2].required_matches, 3)

    def test_rejects_stale_and_low_confidence_states(self) -> None:
        policy = StateAcceptancePolicy(min_confidence=0.8, max_age_ns=100)
        consensus = TableStateConsensus(policy=policy, clock_ns=lambda: NOW_NS)
        stale = consensus.observe(
            "bot-1",
            make_state("stale", frame_ts=NOW_NS - 101),
        )
        weak = consensus.observe(
            "bot-1",
            make_state("weak", confidence=0.79),
        )
        self.assertEqual(stale.rejection_reason, "frame_too_old")
        self.assertEqual(weak.rejection_reason, "confidence_below_threshold")
        self.assertEqual(weak.observed_frames, 0)


if __name__ == "__main__":
    unittest.main()
