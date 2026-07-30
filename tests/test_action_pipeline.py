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


def selected_snapshot(*codes: str) -> PerceptionSnapshot:
    state = snapshot()
    return PerceptionSnapshot(
        bot_id=state.bot_id,
        frame_id="frame-selected",
        frame_ts=state.frame_ts,
        confidence=state.confidence,
        cards=tuple(
            DetectedCard(
                code,
                Rect(100 + 70 * index, 560, 60, 100),
                CardZone.SELECTED,
                0.9,
            )
            for index, code in enumerate(codes)
        ),
        buttons=state.buttons,
    )


class ActionPipelineTests(unittest.TestCase):
    def test_builds_and_executes_card_then_button_taps(self) -> None:
        state = snapshot()
        plan = ActionPlanBuilder().build(
            {"action": "play", "cards": ["3S"], "reason": "test"},
            state,
        )
        controller = StubController()
        taps = ActionTapExecutor(
            controller,
            refresh_snapshot=lambda: selected_snapshot("3S"),
            selection_delay_seconds=0,
        ).execute(plan, state)
        self.assertEqual(plan.kind, ActionKind.PLAY)
        self.assertEqual(controller.taps, [(130, 650), (1060, 630)])
        self.assertEqual(len(taps), 2)

    def test_refuses_a_pass_when_its_button_is_missing(self) -> None:
        with self.assertRaisesRegex(ValueError, "pass button"):
            ActionPlanBuilder().build(
                {"action": "pass"},
                PerceptionSnapshot(
                    bot_id="bot-1",
                    frame_id="frame-1",
                    frame_ts=1,
                    confidence=0.9,
                ),
            )

    def test_a_play_does_not_need_its_button_yet(self) -> None:
        """Responding to another player, the game shows only "Bỏ Lượt"; "Đánh"
        appears once a legal selection exists. Demanding it before the cards are
        selected refused every response the bot ever wanted to make."""
        state = snapshot()
        without_play = PerceptionSnapshot(
            bot_id=state.bot_id, frame_id=state.frame_id, frame_ts=state.frame_ts,
            confidence=state.confidence, cards=state.cards, buttons=(),
        )
        plan = ActionPlanBuilder().build({"action": "play", "cards": ["3S"]}, without_play)
        self.assertEqual(plan.kind, ActionKind.PLAY)
        self.assertEqual(plan.cards, ("3S",))

    def test_refuses_a_play_whose_cards_are_not_on_screen(self) -> None:
        with self.assertRaisesRegex(ValueError, "missing from perception"):
            ActionPlanBuilder().build(
                {"action": "play", "cards": ["3S"]},
                PerceptionSnapshot(
                    bot_id="bot-1", frame_id="frame-1", frame_ts=1, confidence=0.9,
                ),
            )

    def test_refreshes_button_state_after_selecting_card(self) -> None:
        before = snapshot_with_disabled_play()
        after = snapshot()
        plan = ActionPlanBuilder().build({"action": "play", "cards": ["3S"]}, before)
        controller = StubController()
        ActionTapExecutor(
            controller,
            refresh_snapshot=lambda: selected_snapshot("3S"),
            selection_delay_seconds=0,
        ).execute(plan, before)
        self.assertEqual(controller.taps, [(130, 650), (1060, 630)])

class ExactSelectionTests(unittest.TestCase):
    def test_play_requires_a_refresh_to_verify_selection(self) -> None:
        state = snapshot()
        plan = ActionPlanBuilder().build({"action": "play", "cards": ["3S"]}, state)
        controller = StubController()
        with self.assertRaisesRegex(ValueError, "requires refresh_snapshot"):
            ActionTapExecutor(controller).execute(plan, state)
        self.assertEqual(controller.taps, [])

    def test_refuses_to_commit_when_a_wanted_card_is_not_selected(self) -> None:
        state = snapshot()
        plan = ActionPlanBuilder().build({"action": "play", "cards": ["3S"]}, state)
        controller = StubController()
        with self.assertRaisesRegex(ValueError, "missing=3S"):
            ActionTapExecutor(
                controller,
                refresh_snapshot=lambda: selected_snapshot(),
                selection_delay_seconds=0,
            ).execute(plan, state)
        self.assertEqual(controller.taps, [(130, 650)])

    def test_deselects_extras_and_rechecks_before_commit(self) -> None:
        state = snapshot()
        plan = ActionPlanBuilder().build({"action": "play", "cards": ["3S"]}, state)
        refreshed = iter(
            (
                selected_snapshot("3S", "4D"),
                selected_snapshot("3S"),
            )
        )
        controller = StubController()
        taps = ActionTapExecutor(
            controller,
            refresh_snapshot=lambda: next(refreshed),
            selection_delay_seconds=0,
        ).execute(plan, state)
        self.assertEqual([tap.target for tap in taps], ["3S", "-4D", str(ButtonId.PLAY)])
        self.assertEqual(controller.taps[-1], (1060, 630))

    def test_before_commit_runs_only_after_exact_selection(self) -> None:
        state = snapshot()
        plan = ActionPlanBuilder().build({"action": "play", "cards": ["3S"]}, state)
        events: list[str] = []
        ActionTapExecutor(
            StubController(),
            refresh_snapshot=lambda: selected_snapshot("3S"),
            before_commit=lambda: events.append("commit"),
            selection_delay_seconds=0,
        ).execute(plan, state)
        self.assertEqual(events, ["commit"])


class ConfirmTapTests(unittest.TestCase):
    """A tap that did not register is retried once, at the source."""

    def test_a_tap_that_did_not_register_is_repeated(self) -> None:
        state = snapshot()
        plan = ActionPlanBuilder().build({"action": "play", "cards": ["3S"]}, state)
        controller = StubController()
        confirmations = iter((False, True))
        ActionTapExecutor(
            controller,
            confirm_tap=lambda roi: next(confirmations),
            refresh_snapshot=lambda: selected_snapshot("3S"),
            selection_delay_seconds=0,
        ).execute(plan, state)
        # The card is tapped, seen not to have changed, tapped again, then the button.
        self.assertEqual(controller.taps, [(130, 650), (130, 650), (1060, 630)])

    def test_an_unconfirmed_retry_fails_before_the_play_button(self) -> None:
        state = snapshot()
        plan = ActionPlanBuilder().build({"action": "play", "cards": ["3S"]}, state)
        controller = StubController()
        with self.assertRaisesRegex(ValueError, "could not be confirmed"):
            ActionTapExecutor(
                controller,
                confirm_tap=lambda roi: False,
                refresh_snapshot=lambda: selected_snapshot("3S"),
                selection_delay_seconds=0,
            ).execute(plan, state)
        self.assertEqual(controller.taps, [(130, 650), (130, 650)])

    def test_a_tap_that_registered_is_not_repeated(self) -> None:
        state = snapshot()
        plan = ActionPlanBuilder().build({"action": "play", "cards": ["3S"]}, state)
        controller = StubController()
        ActionTapExecutor(
            controller,
            confirm_tap=lambda roi: True,
            refresh_snapshot=lambda: selected_snapshot("3S"),
            selection_delay_seconds=0,
        ).execute(plan, state)
        self.assertEqual(controller.taps, [(130, 650), (1060, 630)])


if __name__ == "__main__":
    unittest.main()
