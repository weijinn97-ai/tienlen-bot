from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Callable, Protocol

from contracts.interfaces import (
    ActionKind,
    ActionPlan,
    ButtonId,
    CardZone,
    PerceptionSnapshot,
    Rect,
    VerifyExpectedChange,
    VerifySpec,
    validate_card_code,
)


class TapController(Protocol):
    def tap(self, x: int, y: int, *, timeout: int = 10) -> str:
        ...


def rect_center(rect: Rect) -> tuple[int, int]:
    return (rect.x + rect.width // 2, rect.y + rect.height // 2)


def union_rect(rects: list[Rect]) -> Rect:
    if not rects:
        raise ValueError("At least one ROI is required.")
    left = min(rect.x for rect in rects)
    top = min(rect.y for rect in rects)
    right = max(rect.x + rect.width for rect in rects)
    bottom = max(rect.y + rect.height for rect in rects)
    return Rect(left, top, right - left, bottom - top)


class ActionPlanBuilder:
    def build(self, decision: dict, snapshot: PerceptionSnapshot) -> ActionPlan:
        action = ActionKind(decision.get("action", "wait"))
        if action == ActionKind.WAIT:
            return ActionPlan(kind=action, reason=decision.get("reason", "wait"))

        target_button = ButtonId.PLAY if action == ActionKind.PLAY else ButtonId.PASS
        button = next(
            (
                candidate
                for candidate in snapshot.buttons
                if candidate.button_id == target_button
                and candidate.is_visible
                and (candidate.is_enabled or action == ActionKind.PLAY)
            ),
            None,
        )
        if button is None:
            raise ValueError(f"Required {target_button.value} button is not available.")

        cards = tuple(validate_card_code(card) for card in decision.get("cards", []))
        verify_rois = [button.roi]
        if action == ActionKind.PLAY:
            detections_by_code = {
                card.code: card
                for card in snapshot.cards
                if card.zone in {CardZone.MY_HAND, CardZone.SELECTED}
            }
            missing = [card for card in cards if card not in detections_by_code]
            if missing:
                raise ValueError(f"Cards are missing from perception: {','.join(missing)}")
            verify_rois.extend(detections_by_code[card].roi for card in cards)

        return ActionPlan(
            kind=action,
            cards=cards,
            target_button=target_button,
            verify_spec=VerifySpec(
                roi=union_rect(verify_rois),
                expected_change=(
                    VerifyExpectedChange.CARD_COUNT_DECREASED
                    if action == ActionKind.PLAY
                    else VerifyExpectedChange.BUTTON_STATE_CHANGED
                ),
                timeout_ms=1500,
                max_retries=2,
            ),
            confidence=min(snapshot.confidence, float(decision.get("confidence", 1.0))),
            reason=decision.get("reason", ""),
        )


@dataclass(frozen=True)
class ExecutedTap:
    target: str
    x: int
    y: int


class ActionTapExecutor:
    def __init__(
        self,
        controller: TapController,
        *,
        refresh_snapshot: Callable[[], PerceptionSnapshot] | None = None,
        selection_delay_seconds: float = 0.2,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.controller = controller
        self.refresh_snapshot = refresh_snapshot
        self.selection_delay_seconds = selection_delay_seconds
        self.sleep = sleep

    def execute(self, plan: ActionPlan, snapshot: PerceptionSnapshot) -> tuple[ExecutedTap, ...]:
        if plan.kind == ActionKind.WAIT:
            return ()
        taps: list[ExecutedTap] = []
        if plan.kind == ActionKind.PLAY:
            detections = {
                card.code: card
                for card in snapshot.cards
                if card.zone in {CardZone.MY_HAND, CardZone.SELECTED}
            }
            for code in plan.cards:
                if code not in detections:
                    raise ValueError(f"Card ROI disappeared before action: {code}")
                x, y = rect_center(detections[code].roi)
                self.controller.tap(x, y)
                taps.append(ExecutedTap(code, x, y))
            if self.refresh_snapshot is not None:
                self.sleep(self.selection_delay_seconds)
                snapshot = self.refresh_snapshot()
        button = next(
            (
                item
                for item in snapshot.buttons
                if item.button_id == plan.target_button and item.is_visible and item.is_enabled
            ),
            None,
        )
        if button is None:
            raise ValueError("Action button disappeared before execution.")
        x, y = rect_center(button.roi)
        self.controller.tap(x, y)
        taps.append(ExecutedTap(str(plan.target_button), x, y))
        return tuple(taps)
