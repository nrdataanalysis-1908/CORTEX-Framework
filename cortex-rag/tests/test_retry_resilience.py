import httpx
import pytest

from openai import APIStatusError

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


def _status_error(status_code: int) -> APIStatusError:
    request = httpx.Request("POST", "https://api.openai.com/v1/embeddings")
    response = httpx.Response(status_code, request=request)
    return APIStatusError(
        message=f"upstream returned {status_code}",
        response=response,
        body={"error": "test"},
    )


@pytest.mark.parametrize("status_code", [408, 409, 429, 500, 503])
def test_openai_transient_http_statuses_are_retryable(status_code):
    assert resilience.is_retryable_openai_error(_status_error(status_code)) is True


@pytest.mark.parametrize("status_code", [400, 401, 403, 404, 422])
def test_openai_permanent_http_statuses_are_not_retryable(status_code):
    assert resilience.is_retryable_openai_error(_status_error(status_code)) is False


def test_unrelated_exceptions_are_not_retryable():
    assert resilience.is_retryable_openai_error(TemporaryFailure()) is False
    assert resilience.is_retryable_openai_error(PermanentFailure()) is False


def test_circuit_breaker_opens_after_failure_threshold():
    breaker = resilience.CircuitBreaker(failure_threshold=2, recovery_timeout_seconds=10)
    failures = 0

    def unavailable():
        nonlocal failures
        failures += 1
        raise TemporaryFailure("upstream unavailable")

    for _ in range(2):
        with pytest.raises(TemporaryFailure):
            breaker.call(unavailable)

    assert failures == 2
    snapshot = breaker.snapshot()
    assert snapshot["state"] == resilience.CircuitBreaker.OPEN
    assert snapshot["consecutive_failures"] == 2
    assert snapshot["transitions"]["closed_to_open"] == 1

    with pytest.raises(resilience.CircuitOpenError):
        breaker.call(lambda: "must not execute")
    assert failures == 2
    assert breaker.snapshot()["rejected_calls"] == 1


def test_circuit_breaker_half_open_probe_recovers():
    now = [100.0]
    breaker = resilience.CircuitBreaker(
        failure_threshold=1,
        recovery_timeout_seconds=5,
        clock=lambda: now[0],
    )

    with pytest.raises(TemporaryFailure):
        breaker.call(lambda: (_ for _ in ()).throw(TemporaryFailure("down")))
    assert breaker.snapshot()["state"] == resilience.CircuitBreaker.OPEN

    now[0] += 5
    assert breaker.call(lambda: "healthy") == "healthy"
    snapshot = breaker.snapshot()
    assert snapshot["state"] == resilience.CircuitBreaker.CLOSED
    assert snapshot["consecutive_failures"] == 0
    assert snapshot["transitions"]["open_to_half_open"] == 1
    assert snapshot["transitions"]["half_open_to_closed"] == 1


def test_circuit_breaker_failed_half_open_probe_reopens():
    now = [10.0]
    breaker = resilience.CircuitBreaker(
        failure_threshold=1,
        recovery_timeout_seconds=3,
        clock=lambda: now[0],
    )

    with pytest.raises(TemporaryFailure):
        breaker.call(lambda: (_ for _ in ()).throw(TemporaryFailure("down")))
    now[0] += 3

    with pytest.raises(TemporaryFailure):
        breaker.call(lambda: (_ for _ in ()).throw(TemporaryFailure("still down")))

    snapshot = breaker.snapshot()
    assert snapshot["state"] == resilience.CircuitBreaker.OPEN
    assert snapshot["transitions"]["half_open_to_open"] == 1


def test_circuit_breaker_allows_only_one_concurrent_half_open_probe():
    import threading

    now = [0.0]
    breaker = resilience.CircuitBreaker(
        failure_threshold=1,
        recovery_timeout_seconds=1,
        clock=lambda: now[0],
    )
    with pytest.raises(TemporaryFailure):
        breaker.call(lambda: (_ for _ in ()).throw(TemporaryFailure("down")))
    now[0] = 1.0

    entered = threading.Event()
    release = threading.Event()
    result = []

    def probe():
        entered.set()
        assert release.wait(timeout=2)
        return "recovered"

    worker = threading.Thread(target=lambda: result.append(breaker.call(probe)))
    worker.start()
    assert entered.wait(timeout=2)

    with pytest.raises(resilience.CircuitOpenError):
        breaker.call(lambda: "second probe must not execute")

    release.set()
    worker.join(timeout=2)
    assert not worker.is_alive()
    assert result == ["recovered"]
    assert breaker.snapshot()["state"] == resilience.CircuitBreaker.CLOSED
    assert breaker.snapshot()["rejected_calls"] == 1


def test_circuit_breaker_does_not_reset_after_stale_concurrent_success():
    import threading

    breaker = resilience.CircuitBreaker(failure_threshold=1, recovery_timeout_seconds=10)
    entered = threading.Event()
    release = threading.Event()
    result = []

    def slow_success():
        entered.set()
        assert release.wait(timeout=2)
        return "late success"

    worker = threading.Thread(target=lambda: result.append(breaker.call(slow_success)))
    worker.start()
    assert entered.wait(timeout=2)

    with pytest.raises(TemporaryFailure):
        breaker.call(lambda: (_ for _ in ()).throw(TemporaryFailure("failure opens circuit")))

    release.set()
    worker.join(timeout=2)
    assert not worker.is_alive()
    assert result == ["late success"]
    assert breaker.snapshot()["state"] == resilience.CircuitBreaker.OPEN


def test_circuit_breaker_rejects_invalid_configuration():
    with pytest.raises(ValueError):
        resilience.CircuitBreaker(failure_threshold=0)
    with pytest.raises(ValueError):
        resilience.CircuitBreaker(recovery_timeout_seconds=0)


def test_circuit_breaker_ignores_permanent_upstream_errors():
    breaker = resilience.CircuitBreaker(failure_threshold=1, recovery_timeout_seconds=10)

    with pytest.raises(PermanentFailure):
        breaker.call(
            lambda: (_ for _ in ()).throw(PermanentFailure("invalid request")),
            is_failure=_is_temporary,
        )

    snapshot = breaker.snapshot()
    assert snapshot["state"] == resilience.CircuitBreaker.CLOSED
    assert snapshot["consecutive_failures"] == 0


def test_permanent_error_during_half_open_probe_confirms_upstream_reachable():
    now = [0.0]
    breaker = resilience.CircuitBreaker(
        failure_threshold=1,
        recovery_timeout_seconds=2,
        clock=lambda: now[0],
    )
    with pytest.raises(TemporaryFailure):
        breaker.call(lambda: (_ for _ in ()).throw(TemporaryFailure("down")))
    now[0] = 2

    with pytest.raises(PermanentFailure):
        breaker.call(
            lambda: (_ for _ in ()).throw(PermanentFailure("invalid request")),
            is_failure=_is_temporary,
        )

    assert breaker.snapshot()["state"] == resilience.CircuitBreaker.CLOSED
