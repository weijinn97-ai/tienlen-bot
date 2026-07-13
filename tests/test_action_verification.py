import unittest

import numpy as np

from bot.actions.verification import FrameDiffVerifier, PostActionVerifier
from contracts.interfaces import Rect, VerifyExpectedChange, VerifySpec


class ActionVerificationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.before = np.zeros((100, 100, 3), dtype=np.uint8)
        self.spec = VerifySpec(
            roi=Rect(20, 20, 30, 30),
            expected_change=VerifyExpectedChange.CARD_COUNT_DECREASED,
            timeout_ms=500,
            max_retries=1,
        )

    def test_roi_diff_is_primary(self) -> None:
        after = self.before.copy()
        after[20:50, 20:50] = 255
        result = PostActionVerifier().verify(
            before_frame=self.before,
            spec=self.spec,
            capture_frame=lambda: after,
        )
        self.assertTrue(result.succeeded)
        self.assertTrue(result.primary_succeeded)
        self.assertFalse(result.escalation_used)

    def test_hand_count_runs_only_after_roi_retries_fail(self) -> None:
        calls = []
        result = PostActionVerifier(FrameDiffVerifier()).verify(
            before_frame=self.before,
            spec=self.spec,
            capture_frame=lambda: self.before.copy(),
            before_hand_count=13,
            parse_hand_count=lambda frame: calls.append(frame) or 12,
        )
        self.assertTrue(result.succeeded)
        self.assertFalse(result.primary_succeeded)
        self.assertTrue(result.escalation_used)
        self.assertEqual(result.attempts, 2)
        self.assertEqual(len(calls), 1)

    def test_both_verification_layers_return_clear_failure(self) -> None:
        result = PostActionVerifier().verify(
            before_frame=self.before,
            spec=self.spec,
            capture_frame=lambda: self.before.copy(),
            before_hand_count=13,
            parse_hand_count=lambda frame: 13,
        )
        self.assertFalse(result.succeeded)
        self.assertEqual(result.reason, "roi_and_hand_count_verification_failed")

    def test_timeout_stops_retries_early(self) -> None:
        times = iter((0.0, 1.0))
        verifier = PostActionVerifier(
            clock=lambda: next(times),
            sleep=lambda seconds: None,
        )
        result = verifier.verify(
            before_frame=self.before,
            spec=self.spec,
            capture_frame=lambda: self.before.copy(),
        )
        self.assertEqual(result.attempts, 1)


if __name__ == "__main__":
    unittest.main()
