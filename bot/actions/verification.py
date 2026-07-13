from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Callable

import numpy as np

from contracts.interfaces import Rect, VerifyExpectedChange, VerifySpec


@dataclass(frozen=True)
class RoiDiffMetrics:
    mean_absolute_diff: float
    changed_pixel_ratio: float


@dataclass(frozen=True)
class VerificationResult:
    succeeded: bool
    primary_succeeded: bool
    escalation_used: bool
    attempts: int
    metrics: RoiDiffMetrics | None
    reason: str


class FrameDiffVerifier:
    def __init__(self, *, min_mean_diff: float = 6.0, min_changed_ratio: float = 0.02) -> None:
        if min_mean_diff < 0 or not 0.0 <= min_changed_ratio <= 1.0:
            raise ValueError("Invalid frame diff thresholds.")
        self.min_mean_diff = min_mean_diff
        self.min_changed_ratio = min_changed_ratio

    def compare(self, before: np.ndarray, after: np.ndarray, roi: Rect) -> RoiDiffMetrics:
        if before.shape != after.shape:
            raise ValueError("Before and after frames must have identical dimensions.")
        if before.ndim != 3 or before.shape[2] < 3:
            raise ValueError("Frames must be HxWx3 arrays.")
        height, width = before.shape[:2]
        if roi.x + roi.width > width or roi.y + roi.height > height:
            raise ValueError("Verify ROI is outside the frame.")
        before_crop = before[roi.y : roi.y + roi.height, roi.x : roi.x + roi.width, :3]
        after_crop = after[roi.y : roi.y + roi.height, roi.x : roi.x + roi.width, :3]
        pixel_diff = np.abs(after_crop.astype(np.int16) - before_crop.astype(np.int16))
        mean_diff = float(np.mean(pixel_diff))
        changed_ratio = float(np.mean(np.max(pixel_diff, axis=2) >= 12))
        return RoiDiffMetrics(mean_diff, changed_ratio)

    def passed(self, metrics: RoiDiffMetrics) -> bool:
        return (
            metrics.mean_absolute_diff >= self.min_mean_diff
            and metrics.changed_pixel_ratio >= self.min_changed_ratio
        )


class PostActionVerifier:
    """Run ROI diff first and hand-count escalation only after all retries fail."""

    def __init__(
        self,
        diff_verifier: FrameDiffVerifier | None = None,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        retry_interval_seconds: float = 0.1,
    ) -> None:
        if retry_interval_seconds < 0:
            raise ValueError("retry_interval_seconds must be non-negative.")
        self.diff_verifier = diff_verifier or FrameDiffVerifier()
        self.clock = clock
        self.sleep = sleep
        self.retry_interval_seconds = retry_interval_seconds

    def verify(
        self,
        *,
        before_frame: np.ndarray,
        spec: VerifySpec,
        capture_frame: Callable[[], np.ndarray],
        before_hand_count: int | None = None,
        parse_hand_count: Callable[[np.ndarray], int | None] | None = None,
    ) -> VerificationResult:
        max_attempts = spec.max_retries + 1
        deadline = self.clock() + spec.timeout_ms / 1000.0
        attempts = 0
        last_frame = before_frame
        last_metrics = None
        for attempt in range(1, max_attempts + 1):
            attempts = attempt
            last_frame = capture_frame()
            last_metrics = self.diff_verifier.compare(before_frame, last_frame, spec.roi)
            if self.diff_verifier.passed(last_metrics):
                return VerificationResult(
                    True,
                    True,
                    False,
                    attempt,
                    last_metrics,
                    "roi_change_confirmed",
                )
            if attempt < max_attempts:
                remaining = deadline - self.clock()
                if remaining <= 0:
                    break
                self.sleep(min(self.retry_interval_seconds, remaining))

        can_escalate = (
            spec.escalate_to_hand_count
            and parse_hand_count is not None
            and before_hand_count is not None
        )
        if can_escalate:
            after_hand_count = parse_hand_count(last_frame)
            expected_decrease = spec.expected_change == VerifyExpectedChange.CARD_COUNT_DECREASED
            count_passed = (
                after_hand_count is not None
                and (
                    after_hand_count < before_hand_count
                    if expected_decrease
                    else after_hand_count != before_hand_count
                )
            )
            if count_passed:
                return VerificationResult(
                    True,
                    False,
                    True,
                    attempts,
                    last_metrics,
                    "hand_count_escalation_confirmed",
                )
            return VerificationResult(
                False,
                False,
                True,
                attempts,
                last_metrics,
                "roi_and_hand_count_verification_failed",
            )
        return VerificationResult(
            False,
            False,
            False,
            attempts,
            last_metrics,
            "roi_verification_failed_no_escalation",
        )
