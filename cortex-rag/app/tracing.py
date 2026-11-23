"""OpenTelemetry bootstrap for CORTEX API tracing.

Export is opt-in: without an OTLP endpoint, spans are not sent externally.
"""
import os

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.psycopg import PsycopgInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


def build_tracer_provider(
    app: FastAPI,
    endpoint: str | None = None,
) -> TracerProvider:
    """Build a provider with bounded service identity and optional OTLP export."""
    provider = TracerProvider(
        resource=Resource.create(
            {
                "service.name": os.getenv("OTEL_SERVICE_NAME", "cortex-rag"),
                "service.version": app.version or "unknown",
            }
        )
    )
    export_endpoint = endpoint or os.getenv(
        "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"
    ) or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if export_endpoint:
        if export_endpoint.rstrip("/").endswith("/v1/traces"):
            resolved_endpoint = export_endpoint
        else:
            resolved_endpoint = f"{export_endpoint.rstrip('/')}/v1/traces"
        provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=resolved_endpoint))
        )
    return provider


def configure_tracing(app: FastAPI) -> None:
    """Configure framework and database spans, exporting only when OTLP is set."""
    trace.set_tracer_provider(build_tracer_provider(app))
    FastAPIInstrumentor.instrument_app(app)
    HTTPXClientInstrumentor().instrument()
    PsycopgInstrumentor().instrument()
