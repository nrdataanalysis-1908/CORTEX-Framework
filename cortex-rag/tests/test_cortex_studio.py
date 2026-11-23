from fastapi.testclient import TestClient
import httpx

from app.config import settings
from app.main import app
import app.cortex_studio as studio


TRACE_ID = "0123456789abcdef0123456789abcdef"
API_KEY = "test_token_with_at_least_32_characters"


def _client(monkeypatch, handler):
    settings.api_access_token = API_KEY
    transport = httpx.MockTransport(handler)

    class MockAsyncClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(studio.httpx, "AsyncClient", MockAsyncClient)
    return TestClient(app)


def test_studio_trace_list_requires_api_key():
    settings.api_access_token = API_KEY
    response = TestClient(app).get("/studio/traces")
    assert response.status_code == 401


def test_studio_trace_list_returns_allowlisted_metadata(monkeypatch):
    def handler(request):
        assert request.url.path == "/api/search"
        return httpx.Response(200, json={"traces": [{
            "traceID": TRACE_ID,
            "rootServiceName": "cortex-rag",
            "rootTraceName": "POST /ask",
            "startTimeUnixNano": "1000000",
            "durationMs": 12.5,
            "spanCount": 3,
            "attributes": {"secret": "must-not-leak"},
        }, {"traceID": "invalid"}]})

    response = _client(monkeypatch, handler).get(
        "/studio/traces?limit=10&lookback_seconds=3600",
        headers={"X-API-Key": API_KEY},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["traces"][0]["trace_id"] == TRACE_ID
    assert "attributes" not in body["traces"][0]


def test_studio_trace_detail_flattens_spans_without_attributes(monkeypatch):
    def handler(request):
        assert request.url.path == f"/api/traces/{TRACE_ID}"
        return httpx.Response(200, json={"batches": [{
            "resource": {"attributes": [{"key": "service.name", "value": {"stringValue": "cortex-rag"}}]},
            "scopeSpans": [{"spans": [{
                "spanId": "abcdef0123456789",
                "parentSpanId": "",
                "name": "POST /ask",
                "startTimeUnixNano": "1000000",
                "endTimeUnixNano": "6000000",
                "attributes": [{"key": "prompt", "value": {"stringValue": "private"}}],
                "status": {"code": 1},
            }]}],
        }]})

    response = _client(monkeypatch, handler).get(
        f"/studio/traces/{TRACE_ID}", headers={"X-API-Key": API_KEY}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["span_count"] == 1
    span = body["spans"][0]
    assert span["service_name"] == "cortex-rag"
    assert span["duration_ms"] == 5
    assert "attributes" not in span
    assert "private" not in response.text


def test_studio_trace_detail_rejects_invalid_trace_id():
    settings.api_access_token = API_KEY
    response = TestClient(app).get(
        "/studio/traces/not-a-trace", headers={"X-API-Key": API_KEY}
    )
    assert response.status_code == 422


def test_studio_maps_tempo_failure_to_service_unavailable(monkeypatch):
    def handler(request):
        return httpx.Response(503)

    response = _client(monkeypatch, handler).get(
        "/studio/traces", headers={"X-API-Key": API_KEY}
    )
    assert response.status_code == 503


def test_studio_ui_is_served_without_exposing_trace_data():
    response = TestClient(app).get("/studio/ui")
    assert response.status_code == 200
    assert "CORTEX Studio" in response.text
    assert "X-API-Key" in response.text
    assert "/studio/traces" in response.text
    assert "localStorage" not in response.text
