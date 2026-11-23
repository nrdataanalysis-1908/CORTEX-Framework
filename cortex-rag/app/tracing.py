"""OpenTelemetry bootstrap for CORTEX API tracing.

Export is opt-in: without OTEL_EXPORTER_OTLP_ENDPOINT, spans are created by
the SDK but are not sent to an external collector.
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


def configure_tracing(app: FastAPI) -> None:
    """Configure framework and database spans, exporting only when OTLP is set."""
    provider = TracerProvider(
        resource=Resource.create(
            {
                "service.name": os.getenv("OTEL_SERVICE_NAME", "cortex-rag"),
                "service.version": app.version or "unknown",
            }
        )
    )
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT") or os.getenv(
        "OTEL_EXPORTER_OTLP_ENDPOINT"
    )
    if endpoint:
        if endpoint.rstrip("/").endswith("/v1/traces"):
            exporter = OTLPSpanExporter(endpoint=endpoint)
        else:
            exporter = OTLPSpanExporter(endpoint=f"{endpoint.rstrip('/')}/v1/traces")
        provider.add_span_processor(BatchSpanProcessor(exporter))

    # A single provider must be installed before instrumentors create spans.
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app)
    HTTPXClientInstrumentor().instrument()
    PsycopgInstrumentor().instrument()
