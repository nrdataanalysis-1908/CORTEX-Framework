# CORTEX Trace Engine — Foundation

## Objective

Establish vendor-neutral distributed tracing before building the CORTEX Studio
interface. The trace contract uses OpenTelemetry so LangGraph, LangChain,
FastAPI, database clients, and future workers can share trace context.

## Current implementation

- FastAPI server spans are created through OpenTelemetry instrumentation.
- HTTPX client spans capture outbound HTTP operations without recording request
  or response bodies by default.
- Psycopg instrumentation creates database client spans.
- Resource attributes identify the service as `cortex-rag` and expose the
  running API version.
- Export is opt-in. Set `OTEL_EXPORTER_OTLP_ENDPOINT` to an OTLP/HTTP
  collector base URL, or `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` to its
  explicit traces endpoint (normally ending in `/v1/traces`).

Example:

```dotenv
OTEL_SERVICE_NAME=cortex-rag
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318
```

No collector is bundled or assumed by this change. Without an endpoint,
instrumentation creates SDK spans but does not persist or export them.

## Data protection

The initial instrumentation does not intentionally capture prompts, document
contents, API keys, or HTTP bodies. Avoid enabling header/body capture in
instrumentation configuration. Trace attributes must remain operational
metadata; user content and secrets require explicit redaction and a separate
data-retention policy before collection.

## Next increments

1. Add stable CORTEX operation spans for ingest, retrieval, embedding, and
   generation, with safe identifiers and bounded attributes.
2. Add a collector and durable trace backend with retention controls.
3. Add LangGraph/LangChain adapters that preserve W3C trace context.
4. Build Studio trace search, run timeline, graph inspection, and replay UI.

## Scope boundary

This foundation is not a LangSmith replacement yet. It supplies standardized
instrumentation, not a trace query API, durable trace store, evaluation UI,
agent graph editor, or replay engine. Those capabilities will be delivered
incrementally and validated independently.
