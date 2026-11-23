# CORTEX Trace Backend

## Components

- OpenTelemetry SDK in the API emits OTLP/HTTP traces.
- OpenTelemetry Collector receives OTLP, applies a bounded memory limiter and
  batches spans before forwarding them to Tempo.
- Grafana Tempo stores trace blocks on the persistent local Docker volume.
- Grafana is provisioned with Tempo as its default data source.

## Local access

After starting the Compose stack:

- Grafana: http://localhost:3000
- Grafana Explore: select the `CORTEX Tempo` data source and query traces.
- Tempo HTTP API is exposed on localhost only at `http://localhost:3200` for readiness and local diagnostics.
- Collector OTLP/HTTP receiver remains internal to the Compose network; its health endpoint is bound to localhost at `http://localhost:13133`.

Grafana is bound to 127.0.0.1 by default. Set a unique
`GRAFANA_ADMIN_PASSWORD` in the untracked `.env` file. Do not expose Grafana,
Tempo, or the Collector receiver directly to the public internet without an
authenticated reverse proxy, TLS, and network controls.

## Retention and durability

Tempo uses local filesystem storage on the `cortex_tempo_data` Docker volume
with a 72-hour block retention policy. This is a single-node development and
evaluation configuration, not a production high-availability design. Back up
the volume if the trace history matters. For production, move trace blocks to
object storage (S3, GCS, or Azure Blob Storage) and define explicit retention,
backup, access-control, and deletion policies.

## Resource controls

Compose applies container-level memory, CPU, and PID limits to Tempo, the
Collector, and Grafana. These limits are guardrails for a local stack and must
be sized from observed telemetry volume and query load.

## Data handling

Do not attach prompts, document contents, credentials, authorization headers,
or raw HTTP bodies to spans. Trace attributes should use operational metadata
and opaque identifiers. Define redaction and access policies before adding
custom span attributes or broader instrumentation.

## Scope

This increment provides trace collection, local persistence, and a UI through
Grafana Explore. It does not yet provide the custom CORTEX Studio frontend,
LangGraph graph visualization, run replay, evaluation workflows, or a
multi-tenant trace authorization model.
