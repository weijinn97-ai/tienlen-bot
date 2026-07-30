from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Callable, Protocol

from contracts.interfaces import (
    ActionKind,
    ActionPlan,
    ButtonId,
    CardZone,
    DetectedCard,
    PerceptionSnapshot,
    Rect,
    VerifyExpectedChange,
    VerifySpec,
    validate_card_code,
)


class TapController(Protocol):
    def tap(self, x: int, y: int, *, timeout: int = 10) -> str:
        ...


class TapConfirmer(Protocol):
    """Reports whether the last tap changed anything inside a region."""

    def __call__(self, roi: Rect) -> bool:
        ...


def rect_center(rect: Rect) -> tuple[int, int]:
    return (rect.x + rect.width // 2, rect.y + rect.height // 2)


def playable_by_code(snapshot: PerceptionSnapshot) -> dict[str, "DetectedCard"]:
    """Map each code to its detection, preferring the selected copy.

    The reader can report the same code in both zones at once - a card lifted out
    of the fan and another read at its old position - and a plain dict keeps
    whichever came last. If that is the unselected copy, tapping it toggles the
    real selection off and the turn never completes.
    """
    playable: dict[str, "DetectedCard"] = {}
    for card in snapshot.cards:
        if card.zone not in {CardZone.MY_HAND, CardZone.SELECTED}:
            continue
        existing = playable.get(card.code)
        if existing is None or (
            existing.zone is not CardZone.SELECTED and card.zone is CardZone.SELECTED
        ):
            playable[card.code] = card
    return playable


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
        # Responding to another player, the game shows only "Bỏ Lượt"; "Đánh"
        # appears once a legal selection exists. Requiring it before the cards
        # are selected refused every response the bot ever wanted to make - it
        # sat on a pair of 5s and a pair of 8s against a pair of 4s and did
        # nothing. For a play, the button is looked for again after selection.
        if button is None and action != ActionKind.PLAY:
            raise ValueError(f"Required {target_button.value} button is not available.")

        cards = tuple(validate_card_code(card) for card in decision.get("cards", []))
        verify_rois = [button.roi] if button is not None else []
        if action == ActionKind.PLAY:
            detections_by_code = playable_by_code(snapshot)
            missing = [card for card in cards if card not in detections_by_code]
            if missing:
                raise ValueError(f"Cards are missing from perception: {','.join(missing)}")
            verify_rois.extend(detections_by_code[card].roi for card in cards)
        if not verify_rois:
            raise ValueError(f"Nothing to verify for a {action.value} action.")

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
        confirm_tap: TapConfirmer | None = None,
        before_commit: Callable[[], None] | None = None,
        selection_delay_seconds: float = 0.2,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.controller = controller
        self.refresh_snapshot = refresh_snapshot
        self.confirm_tap = confirm_tap
        self.before_commit = before_commit
        self.selection_delay_seconds = selection_delay_seconds
        self.sleep = sleep

    def execute(
        self,
        plan: ActionPlan,
        snapshot: PerceptionSnapshot,
    ) -> tuple[ExecutedTap, ...]:
        """Carry out a plan, refusing to commit an unverified card selection."""
        if plan.kind == ActionKind.WAIT:
            return ()
        taps: list[ExecutedTap] = []
        if plan.kind == ActionKind.PLAY:
            if self.refresh_snapshot is None:
                raise ValueError(
                    "PLAY requires refresh_snapshot to verify the exact selection."
                )
            detections = playable_by_code(snapshot)
            for code in plan.cards:
                if code not in detections:
                    raise ValueError(f"Card ROI disappeared before action: {code}")
                # Tapping is a toggle. A card already lifted out of the fan is
                # selected, so tapping it again would deselect it and the turn
                # would loop until the clock ran out.
                if detections[code].zone is CardZone.SELECTED:
                    continue
                roi = detections[code].roi
                x, y = rect_center(roi)
                self.controller.tap(x, y)
                taps.append(ExecutedTap(code, x, y))
                # A tap that did not register leaves the card unselected, and the
                # next look would decide the same play and tap again - which by
                # then toggles a selection that did take. Confirming here breaks
                # that cycle at its source. Measured on 22 taps we made
                # deliberately, a registered tap changed at least 19.8% of the
                # card's own pixels while an untouched region changed none.
                if self.confirm_tap is not None and not self.confirm_tap(roi):
                    self.controller.tap(x, y)
                    taps.append(ExecutedTap(f"{code}(lai)", x, y))
                    if not self.confirm_tap(roi):
                        raise ValueError(f"Card tap could not be confirmed after retry: {code}")

            self.sleep(self.selection_delay_seconds)
            snapshot = self.refresh_snapshot()
            extra_taps = self._deselect_extras(plan, snapshot)
            taps.extend(extra_taps)
            if extra_taps:
                self.sleep(self.selection_delay_seconds)
                snapshot = self.refresh_snapshot()
            self._require_exact_selection(plan, snapshot)

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

        if self.before_commit is not None:
            self.before_commit()
        x, y = rect_center(button.roi)
        self.controller.tap(x, y)
        taps.append(ExecutedTap(str(plan.target_button), x, y))
        return tuple(taps)

    def _deselect_extras(
        self, plan: ActionPlan, snapshot: PerceptionSnapshot
    ) -> list[ExecutedTap]:
        """Clear selected cards outside the plan, then force another refresh.

        A card left selected from an earlier turn, or picked up by a stray tap,
        would be played alongside the intended ones and make the combo illegal.
        Re-reading after the selection taps is the only chance to notice.
        """
        wanted = set(plan.cards)
        taps: list[ExecutedTap] = []
        extras = sorted(
            (card for card in snapshot.cards
             if card.zone is CardZone.SELECTED and card.code not in wanted),
            key=lambda card: card.code,
        )
        for card in extras:
            x, y = rect_center(card.roi)
            self.controller.tap(x, y)
            taps.append(ExecutedTap(f"-{card.code}", x, y))
        return taps

    @staticmethod
    def _require_exact_selection(
        plan: ActionPlan, snapshot: PerceptionSnapshot
    ) -> None:
        """Fail closed unless perception proves the selected set equals the plan."""
        selected = {
            card.code for card in snapshot.cards if card.zone is CardZone.SELECTED
        }
        wanted = set(plan.cards)
        if selected != wanted:
            missing = ",".join(sorted(wanted - selected)) or "-"
            extras = ",".join(sorted(selected - wanted)) or "-"
            raise ValueError(
                "Exact card selection was not verified "
                f"(missing={missing}; extra={extras})."
            )
