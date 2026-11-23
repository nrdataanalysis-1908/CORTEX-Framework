from fastapi import FastAPI
from opentelemetry import trace

from app.tracing import configure_tracing


def test_tracing_configures_service_resource_without_exporter(monkeypatch):
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", raising=False)
    app = FastAPI(version="test")
    configure_tracing(app)

    provider = trace.get_tracer_provider()
    resource = provider.resource.attributes
    assert resource["service.name"] == "cortex-rag"
    assert resource["service.version"] == "test"
