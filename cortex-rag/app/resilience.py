import random
import threading
import time
from collections.abc import Callable
from typing import TypeVar

from openai import APIConnectionError, APIStatusError, APITimeoutError, InternalServerError, RateLimitError

from app.config import settings

T = TypeVar("T")


def is_retryable_openai_error(error: Exception) -> bool:
    """Retry network/timeouts, rate limits and transient HTTP responses only."""
    if isinstance(error, (APIConnectionError, APITimeoutError, RateLimitError, InternalServerError)):
        return True
    if isinstance(error, APIStatusError):
        return error.status_code in {408, 409, 429} or error.status_code >= 500
    return False


def retry_call(
    operation: str,
    call: Callable[[], T],
    *,
    max_retries: int,
    base_delay_seconds: float,
    max_delay_seconds: float,
    is_retryable: Callable[[Exception], bool],
    on_retry: Callable[[str, int, float], None] | None = None,
    on_recovered: Callable[[str, int], None] | None = None,
    on_exhausted: Callable[[str, int], None] | None = None,
    on_permanent_failure: Callable[[str], None] | None = None,
) -> T:
    """Execute a call with bounded exponential backoff and full jitter.

    max_retries counts retries after the initial attempt. Permanent errors are
    propagated immediately; transient errors are propagated after exhaustion.
    """
    for attempt in range(max_retries + 1):
        try:
            result = call()
            if attempt and on_recovered:
                on_recovered(operation, attempt)
            return result
        except Exception as error:
            if not is_retryable(error):
                if on_permanent_failure and not isinstance(error, BulkheadFullError):
                    on_permanent_failure(operation)
                raise
            if attempt >= max_retries:
                if on_exhausted:
                    on_exhausted(operation, attempt + 1)
                raise

            ceiling = min(max_delay_seconds, base_delay_seconds * (2**attempt))
            delay = random.uniform(0.0, ceiling)
            if on_retry:
                on_retry(operation, attempt + 1, delay)
            time.sleep(delay)

    raise RuntimeError("Unreachable retry state")


class CircuitOpenError(RuntimeError):
    """Raised when the upstream circuit is open or a half-open probe is busy."""

    def __init__(self, retry_after_seconds: float):
        self.retry_after_seconds = max(0.0, retry_after_seconds)
        super().__init__("Upstream circuit breaker is open")


class CircuitBreaker:
    """Thread-safe, process-local circuit breaker with a single half-open probe."""

    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"

    def __init__(
        self,
        *,
        failure_threshold: int = 5,
        recovery_timeout_seconds: float = 30.0,
        clock: Callable[[], float] = time.monotonic,
    ):
        if failure_threshold < 1:
            raise ValueError("failure_threshold must be at least 1")
        if recovery_timeout_seconds <= 0:
            raise ValueError("recovery_timeout_seconds must be positive")
        self.failure_threshold = failure_threshold
        self.recovery_timeout_seconds = recovery_timeout_seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._state = self.CLOSED
        self._failure_count = 0
        self._opened_at: float | None = None
        self._probe_in_flight = False
        self._state_transitions = {"closed_to_open": 0, "open_to_half_open": 0, "half_open_to_open": 0, "half_open_to_closed": 0}
        self._rejected_calls = 0
        self._epoch = 0

    def _open_locked(self, now: float, *, from_state: str) -> None:
        self._state = self.OPEN
        self._opened_at = now
        self._probe_in_flight = False
        self._epoch += 1
        transition = "half_open_to_open" if from_state == self.HALF_OPEN else "closed_to_open"
        self._state_transitions[transition] += 1

    def call(
        self,
        operation: Callable[[], T],
        *,
        is_failure: Callable[[Exception], bool] = lambda error: True,
        is_ignored: Callable[[Exception], bool] = lambda error: False,
    ) -> T:
        now = self._clock()
        with self._lock:
            if self._state == self.OPEN:
                elapsed = now - (self._opened_at if self._opened_at is not None else now)
                if elapsed < self.recovery_timeout_seconds:
                    self._rejected_calls += 1
                    raise CircuitOpenError(self.recovery_timeout_seconds - elapsed)
                self._state = self.HALF_OPEN
                self._probe_in_flight = False
                self._state_transitions["open_to_half_open"] += 1

            if self._state == self.HALF_OPEN:
                if self._probe_in_flight:
                    self._rejected_calls += 1
                    raise CircuitOpenError(0.0)
                self._probe_in_flight = True
                call_state = self.HALF_OPEN
                call_epoch = self._epoch
            else:
                call_state = self.CLOSED
                call_epoch = self._epoch

        try:
            result = operation()
        except Exception as error:
            with self._lock:
                failed = is_failure(error)
                if call_state == self.HALF_OPEN and self._state == self.HALF_OPEN and call_epoch == self._epoch:
                    if is_ignored(error):
                        # No upstream probe occurred (for example, local capacity was full).
                        self._probe_in_flight = False
                    elif failed:
                        self._open_locked(self._clock(), from_state=self.HALF_OPEN)
                    else:
                        # A permanent response (for example HTTP 400/401) proves
                        # the upstream is reachable; propagate it without keeping
                        # the circuit open.
                        self._close_after_probe_locked()
                elif failed and call_state == self.CLOSED and self._state == self.CLOSED and call_epoch == self._epoch:
                    self._failure_count += 1
                    if self._failure_count >= self.failure_threshold:
                        self._open_locked(self._clock(), from_state=self.CLOSED)
            raise

        with self._lock:
            if call_state == self.HALF_OPEN and self._state == self.HALF_OPEN and call_epoch == self._epoch:
                self._state = self.CLOSED
                self._failure_count = 0
                self._opened_at = None
                self._probe_in_flight = False
                self._epoch += 1
                self._state_transitions["half_open_to_closed"] += 1
            elif call_state == self.CLOSED and self._state == self.CLOSED and call_epoch == self._epoch:
                self._failure_count = 0
        return result

    def _close_after_probe_locked(self) -> None:
        self._state = self.CLOSED
        self._failure_count = 0
        self._opened_at = None
        self._probe_in_flight = False
        self._epoch += 1
        self._state_transitions["half_open_to_closed"] += 1

    def snapshot(self) -> dict:
        now = self._clock()
        with self._lock:
            retry_after = 0.0
            if self._state == self.OPEN and self._opened_at is not None:
                retry_after = max(0.0, self.recovery_timeout_seconds - (now - self._opened_at))
            return {
                "scope": "process_local",
                "state": self._state,
                "consecutive_failures": self._failure_count,
                "failure_threshold": self.failure_threshold,
                "recovery_timeout_seconds": self.recovery_timeout_seconds,
                "retry_after_seconds": round(retry_after, 3),
                "half_open_probe_in_flight": self._probe_in_flight,
                "rejected_calls": self._rejected_calls,
                "transitions": dict(self._state_transitions),
            }


upstream_circuit_breaker = CircuitBreaker(
    failure_threshold=settings.circuit_breaker_failure_threshold,
    recovery_timeout_seconds=settings.circuit_breaker_recovery_timeout_seconds,
)


class BulkheadFullError(RuntimeError):
    """Raised when an upstream operation has exhausted its concurrency capacity."""

    def __init__(self, operation: str, max_concurrency: int):
        self.operation = operation
        self.max_concurrency = max_concurrency
        self.retry_after_seconds = 1.0
        super().__init__(f"Bulkhead capacity exhausted for {operation}")


class Bulkhead:
    """Thread-safe, non-waiting concurrency limiter for one upstream operation."""

    def __init__(self, name: str, max_concurrency: int):
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be at least 1")
        self.name = name
        self.max_concurrency = max_concurrency
        self._lock = threading.Lock()
        self._in_flight = 0
        self._rejected_calls = 0

    def call(self, operation: Callable[[], T]) -> T:
        with self._lock:
            if self._in_flight >= self.max_concurrency:
                self._rejected_calls += 1
                raise BulkheadFullError(self.name, self.max_concurrency)
            self._in_flight += 1
        try:
            return operation()
        finally:
            with self._lock:
                self._in_flight -= 1

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "max_concurrency": self.max_concurrency,
                "in_flight": self._in_flight,
                "rejected_calls": self._rejected_calls,
            }


embedding_bulkhead = Bulkhead(
    "embeddings", settings.embedding_max_concurrency
)
chat_bulkhead = Bulkhead(
    "chat", settings.chat_max_concurrency
)
