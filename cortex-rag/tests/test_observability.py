from app.observability import metrics_snapshot, record_request


def test_metrics_snapshot_exposes_request_count_and_latency():
    before = metrics_snapshot()["request_count"]
    record_request("GET", "/health", 200, 12.5, "test-request")
    snapshot = metrics_snapshot()

    assert snapshot["request_count"] == before + 1
    assert snapshot["server_error_count"] >= 0
    assert snapshot["latency_ms"]["sample_count"] >= 1
    assert snapshot["latency_ms"]["p50"] is not None
    assert snapshot["scope"] == "process_local"


def test_error_rate_counts_server_errors():
    before = metrics_snapshot()
    record_request("POST", "/ask", 502, 30.0, "test-error")
    after = metrics_snapshot()

    assert after["server_error_count"] == before["server_error_count"] + 1
