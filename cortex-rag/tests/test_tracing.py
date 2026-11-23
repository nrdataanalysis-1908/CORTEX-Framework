from fastapi import FastAPI

from app.tracing import build_tracer_provider


def test_tracer_provider_has_service_identity_without_exporter(monkeypatch):
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", raising=False)
    app = FastAPI(version="test")

    provider = build_tracer_provider(app)

    assert provider.resource.attributes["service.name"] == "cortex-rag"
    assert provider.resource.attributes["service.version"] == "test"
    assert provider._active_span_processor._span_processors == ()
