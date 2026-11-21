import logging
import threading
from collections import deque

logger = logging.getLogger("cortex.request")
_lock = threading.Lock()
_request_count = 0
_error_count = 0
_retry_attempt_count = 0
_retry_recovered_count = 0
_retry_exhausted_count = 0
_retry_permanent_failure_count = 0
_recent_durations_ms = deque(maxlen=10_000)


def record_request(method: str, path: str, status_code: int, duration_ms: float, request_id: str) -> None:
    global _request_count, _error_count
    with _lock:
        _request_count += 1
        if status_code >= 500:
            _error_count += 1
        _recent_durations_ms.append(duration_ms)
    logger.info(
        "http_request",
        extra={
            "method": method,
            "path": path,
            "status_code": status_code,
            "duration_ms": round(duration_ms, 3),
            "request_id": request_id,
        },
    )


def record_retry_attempt(operation: str, attempt: int, delay_seconds: float) -> None:
    global _retry_attempt_count
    with _lock:
        _retry_attempt_count += 1
    logger.warning(
        "upstream_retry",
        extra={"operation": operation, "attempt": attempt, "delay_seconds": round(delay_seconds, 4)},
    )


def record_retry_recovered(operation: str, attempts: int) -> None:
    global _retry_recovered_count
    with _lock:
        _retry_recovered_count += 1
    logger.info("upstream_retry_recovered", extra={"operation": operation, "attempts": attempts})


def record_retry_exhausted(operation: str, attempts: int) -> None:
    global _retry_exhausted_count
    with _lock:
        _retry_exhausted_count += 1
    logger.error("upstream_retry_exhausted", extra={"operation": operation, "attempts": attempts})


def record_permanent_failure(operation: str) -> None:
    global _retry_permanent_failure_count
    with _lock:
        _retry_permanent_failure_count += 1
    logger.error("upstream_permanent_failure", extra={"operation": operation})


def metrics_snapshot() -> dict:
    with _lock:
        durations = sorted(_recent_durations_ms)
        request_count = _request_count
        error_count = _error_count
        retry_metrics = {
            "attempt_count": _retry_attempt_count,
            "recovered_count": _retry_recovered_count,
            "exhausted_count": _retry_exhausted_count,
            "permanent_failure_count": _retry_permanent_failure_count,
        }

    def percentile(values: list[float], quantile: float) -> float | None:
        if not values:
            return None
        index = max(0, min(len(values) - 1, int((len(values) * quantile) + 0.999999) - 1))
        return round(values[index], 3)

    from app.resilience import chat_bulkhead, embedding_bulkhead, upstream_circuit_breaker

    return {
        "scope": "process_local",
        "request_count": request_count,
        "server_error_count": error_count,
        "server_error_rate": round(error_count / request_count, 4) if request_count else 0.0,
        "latency_ms": {
            "sample_count": len(durations),
            "p50": percentile(durations, 0.50),
            "p95": percentile(durations, 0.95),
            "p99": percentile(durations, 0.99),
        },
        "upstream_retries": retry_metrics,
        "upstream_circuit_breaker": upstream_circuit_breaker.snapshot(),
        "upstream_bulkheads": {
            "embeddings": embedding_bulkhead.snapshot(),
            "chat": chat_bulkhead.snapshot(),
        },
        "note": "Métricas em memória do processo; reiniciam com a aplicação e não substituem monitoramento distribuído.",
    }
