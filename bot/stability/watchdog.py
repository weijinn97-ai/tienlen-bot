from __future__ import annotations

from dataclasses import dataclass
import time


@dataclass(frozen=True)
class CircuitBreakerState:
    is_open: bool
    failure_count: int
    last_error: str | None
    opened_at_ns: int | None


class CircuitBreaker:
    def __init__(self, *, failure_threshold: int = 3) -> None:
        if failure_threshold < 1:
            raise ValueError("failure_threshold must be positive.")

        self.failure_threshold = failure_threshold
        self._failure_count = 0
        self._last_error: str | None = None
        self._opened_at_ns: int | None = None

    def record_success(self) -> None:
        self._failure_count = 0
        self._last_error = None
        self._opened_at_ns = None

    def record_failure(self, error_message: str) -> CircuitBreakerState:
        self._failure_count += 1
        self._last_error = error_message
        if self._failure_count >= self.failure_threshold and self._opened_at_ns is None:
            self._opened_at_ns = time.monotonic_ns()
        return self.state

    def close(self) -> None:
        self.record_success()

    @property
    def state(self) -> CircuitBreakerState:
        return CircuitBreakerState(
            is_open=self._opened_at_ns is not None,
            failure_count=self._failure_count,
            last_error=self._last_error,
            opened_at_ns=self._opened_at_ns,
        )
