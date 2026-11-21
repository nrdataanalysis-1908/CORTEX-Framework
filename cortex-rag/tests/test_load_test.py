import pytest

from evaluation.load_test import percentile, summarize


def test_percentile_uses_nearest_rank():
    assert percentile([50, 10, 30, 20, 40], 0.50) == 30
    assert percentile([50, 10, 30, 20, 40], 0.95) == 50
    assert percentile([], 0.95) is None


def test_summarize_reports_latency_throughput_and_failures():
    report = summarize(
        [
            {"status": 200, "success": True, "latency_ms": 10.0},
            {"status": 200, "success": True, "latency_ms": 20.0},
            {"status": 503, "success": False, "latency_ms": 30.0},
        ],
        2.0,
        concurrency=2,
    )
    assert report["requests"] == 3
    assert report["successful_requests"] == 2
    assert report["failed_requests"] == 1
    assert report["error_rate"] == pytest.approx(1 / 3, abs=0.0001)
    assert report["throughput_requests_per_second"] == 1.5
    assert report["latency_ms"]["p50"] == 20.0
    assert report["latency_ms"]["p95"] == 30.0
    assert report["status_counts"] == {"200": 2, "503": 1}


def test_summarize_handles_no_latency_samples():
    report = summarize(
        [{"status": "network_error", "success": False, "latency_ms": None}],
        1.0,
        concurrency=1,
    )
    assert report["latency_ms"]["p99"] is None
    assert report["failed_requests"] == 1


@pytest.mark.parametrize(
    "kwargs",
    [
        {"requests": 0, "concurrency": 1, "warmup": 0, "timeout": 1},
        {"requests": 1, "concurrency": 0, "warmup": 0, "timeout": 1},
        {"requests": 1, "concurrency": 1, "warmup": -1, "timeout": 1},
        {"requests": 1, "concurrency": 1, "warmup": 0, "timeout": 0},
    ],
)
def test_run_load_test_rejects_invalid_parameters(kwargs):
    from evaluation.load_test import run_load_test

    with pytest.raises(ValueError):
        run_load_test("http://localhost:8000/ask", {"question": "test"}, **kwargs)
