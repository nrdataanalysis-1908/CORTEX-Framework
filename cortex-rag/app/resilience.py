import random
import time
from collections.abc import Callable
from typing import TypeVar

from openai import APIConnectionError, APIStatusError, APITimeoutError, InternalServerError, RateLimitError

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
                if on_permanent_failure:
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
