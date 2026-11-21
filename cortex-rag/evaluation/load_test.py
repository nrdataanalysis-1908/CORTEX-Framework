"""Reproducible, dependency-free HTTP load test for the CORTEX RAG API.

Example:
  python -m evaluation.load_test --url http://127.0.0.1:8000/ask \
      --requests 100 --concurrency 10 --warmup 5 \
      --payload '{"question":"Qual é o procedimento de contingência?"}'
"""
from __future__ import annotations

import argparse
import json
import math
import time
import uuid
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def percentile(values: list[float], quantile: float) -> float | None:
    """Return nearest-rank percentile in milliseconds."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(quantile * len(ordered)))
    return round(ordered[rank - 1], 3)


def summarize(results: list[dict], elapsed_seconds: float, *, concurrency: int) -> dict:
    latencies = [item["latency_ms"] for item in results if item["latency_ms"] is not None]
    status_counts = Counter(str(item["status"]) for item in results)
    successes = sum(1 for item in results if item["success"])
    total = len(results)
    return {
        "requests": total,
        "successful_requests": successes,
        "failed_requests": total - successes,
        "error_rate": round((total - successes) / total, 4) if total else 0.0,
        "concurrency": concurrency,
        "duration_seconds": round(elapsed_seconds, 3),
        "throughput_requests_per_second": round(total / elapsed_seconds, 3) if elapsed_seconds > 0 else 0.0,
        "latency_ms": {
            "min": round(min(latencies), 3) if latencies else None,
            "mean": round(sum(latencies) / len(latencies), 3) if latencies else None,
            "p50": percentile(latencies, 0.50),
            "p95": percentile(latencies, 0.95),
            "p99": percentile(latencies, 0.99),
            "max": round(max(latencies), 3) if latencies else None,
            "sample_count": len(latencies),
        },
        "status_counts": dict(sorted(status_counts.items())),
    }


def execute_request(url: str, payload: bytes, timeout: float) -> dict:
    request = Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Request-ID": str(uuid.uuid4()),
        },
        method="POST",
    )
    started = time.perf_counter()
    try:
        with urlopen(request, timeout=timeout) as response:
            response.read()
            status = response.status
        return {"status": status, "success": 200 <= status < 400,
                "latency_ms": (time.perf_counter() - started) * 1000}
    except HTTPError as error:
        error.read()
        return {"status": error.code, "success": False,
                "latency_ms": (time.perf_counter() - started) * 1000}
    except (URLError, TimeoutError, OSError):
        return {"status": "network_error", "success": False,
                "latency_ms": (time.perf_counter() - started) * 1000}


def run_load_test(
    url: str,
    payload: dict,
    *,
    requests: int,
    concurrency: int,
    warmup: int = 0,
    timeout: float = 60.0,
) -> dict:
    if requests < 1 or concurrency < 1 or warmup < 0 or timeout <= 0:
        raise ValueError("requests/concurrency/timeout must be positive and warmup non-negative")
    body = json.dumps(payload).encode("utf-8")

    for _ in range(warmup):
        execute_request(url, body, timeout)

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(execute_request, url, body, timeout) for _ in range(requests)]
        results = [future.result() for future in as_completed(futures)]
    elapsed = time.perf_counter() - started
    return summarize(results, elapsed, concurrency=concurrency)


def main() -> int:
    parser = argparse.ArgumentParser(description="CORTEX RAG HTTP load-test baseline")
    parser.add_argument("--url", required=True, help="Full API URL, e.g. http://localhost:8000/ask")
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--warmup", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--payload", default='{"question":"Informe o procedimento documentado."}')
    parser.add_argument("--fail-on-error", action="store_true")
    args = parser.parse_args()
    try:
        payload = json.loads(args.payload)
        if not isinstance(payload, dict):
            raise ValueError("payload must be a JSON object")
        report = run_load_test(
            args.url, payload, requests=args.requests, concurrency=args.concurrency,
            warmup=args.warmup, timeout=args.timeout,
        )
    except (ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if args.fail_on_error and report["failed_requests"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
