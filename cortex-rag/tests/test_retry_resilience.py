import pytest

from app import resilience


class TemporaryFailure(Exception):
    pass


class PermanentFailure(Exception):
    pass


def _is_temporary(error: Exception) -> bool:
    return isinstance(error, TemporaryFailure)


def test_retry_call_recovers_after_transient_failures(monkeypatch):
    calls = 0
    delays = []
    recovered = []

    def flaky_call():
        nonlocal calls
        calls += 1
        if calls < 3:
            raise TemporaryFailure("temporary upstream outage")
        return "ok"

    monkeypatch.setattr(resilience.random, "uniform", lambda low, high: high)
    monkeypatch.setattr(resilience.time, "sleep", delays.append)

    result = resilience.retry_call(
        "test.operation",
        flaky_call,
        max_retries=3,
        base_delay_seconds=0.5,
        max_delay_seconds=2.0,
        is_retryable=_is_temporary,
        on_recovered=lambda operation, attempts: recovered.append((operation, attempts)),
    )

    assert result == "ok"
    assert calls == 3
    assert delays == [0.5, 1.0]
    assert recovered == [("test.operation", 2)]


def test_retry_call_does_not_retry_permanent_failures(monkeypatch):
    calls = 0
    delays = []
    permanent = []

    def invalid_call():
        nonlocal calls
        calls += 1
        raise PermanentFailure("invalid request")

    monkeypatch.setattr(resilience.time, "sleep", delays.append)

    with pytest.raises(PermanentFailure, match="invalid request"):
        resilience.retry_call(
            "test.operation",
            invalid_call,
            max_retries=4,
            base_delay_seconds=0.5,
            max_delay_seconds=2.0,
            is_retryable=_is_temporary,
            on_permanent_failure=permanent.append,
        )

    assert calls == 1
    assert delays == []
    assert permanent == ["test.operation"]


def test_retry_call_stops_after_configured_attempts(monkeypatch):
    calls = 0
    delays = []
    exhausted = []

    def unavailable_call():
        nonlocal calls
        calls += 1
        raise TemporaryFailure("still unavailable")

    monkeypatch.setattr(resilience.random, "uniform", lambda low, high: high)
    monkeypatch.setattr(resilience.time, "sleep", delays.append)

    with pytest.raises(TemporaryFailure, match="still unavailable"):
        resilience.retry_call(
            "test.operation",
            unavailable_call,
            max_retries=2,
            base_delay_seconds=0.25,
            max_delay_seconds=1.0,
            is_retryable=_is_temporary,
            on_exhausted=lambda operation, attempts: exhausted.append((operation, attempts)),
        )

    assert calls == 3
    assert delays == [0.25, 0.5]
    assert exhausted == [("test.operation", 3)]


def test_openai_error_classification_rejects_unrelated_errors():
    assert resilience.is_retryable_openai_error(TemporaryFailure()) is False
    assert resilience.is_retryable_openai_error(PermanentFailure()) is False
