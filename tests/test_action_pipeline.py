import unittest

from bot.actions.action_pipeline import ActionPlanBuilder, ActionTapExecutor
from contracts.interfaces import (
    ActionKind,
    ButtonId,
    ButtonState,
    CardZone,
    DetectedCard,
    PerceptionSnapshot,
    Rect,
)


class StubController:
    def __init__(self) -> None:
        self.taps = []

    def tap(self, x, y, *, timeout=10):
        self.taps.append((x, y))
        return ""


def snapshot() -> PerceptionSnapshot:
    return PerceptionSnapshot(
        bot_id="bot-1",
        frame_id="frame-1",
        frame_ts=1,
        confidence=0.95,
        cards=(DetectedCard("3S", Rect(100, 600, 60, 100), CardZone.MY_HAND, 0.9),),
        buttons=(ButtonState(ButtonId.PLAY, "Danh", Rect(1000, 600, 120, 60)),),
    )


def snapshot_with_disabled_play() -> PerceptionSnapshot:
    state = snapshot()
    return PerceptionSnapshot(
        bot_id=state.bot_id,
        frame_id=state.frame_id,
        frame_ts=state.frame_ts,
        confidence=state.confidence,
        cards=state.cards,
        buttons=(ButtonState(ButtonId.PLAY, "Danh", Rect(1000, 600, 120, 60), is_enabled=False),),
    )


class ActionPipelineTests(unittest.TestCase):
    def test_builds_and_executes_card_then_button_taps(self) -> None:
        state = snapshot()
        plan = ActionPlanBuilder().build(
            {"action": "play", "cards": ["3S"], "reason": "test"},
            state,
        )
        controller = StubController()
        taps = ActionTapExecutor(controller).execute(plan, state)
        self.assertEqual(plan.kind, ActionKind.PLAY)
        self.assertEqual(controller.taps, [(130, 650), (1060, 630)])
        self.assertEqual(len(taps), 2)

    def test_refuses_action_when_required_button_is_missing(self) -> None:
        with self.assertRaisesRegex(ValueError, "play button"):
            ActionPlanBuilder().build(
                {"action": "play", "cards": ["3S"]},
                PerceptionSnapshot(
                    bot_id="bot-1",
                    frame_id="frame-1",
                    frame_ts=1,
                    confidence=0.9,
                ),
            )

    def test_refreshes_button_state_after_selecting_card(self) -> None:
        before = snapshot_with_disabled_play()
        after = snapshot()
        plan = ActionPlanBuilder().build({"action": "play", "cards": ["3S"]}, before)
        controller = StubController()
        ActionTapExecutor(
            controller,
            refresh_snapshot=lambda: after,
            selection_delay_seconds=0,
        ).execute(plan, before)
        self.assertEqual(controller.taps, [(130, 650), (1060, 630)])


if __name__ == "__main__":
    unittest.main()
