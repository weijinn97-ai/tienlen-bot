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


if __name__ == "__main__":
    unittest.main()
