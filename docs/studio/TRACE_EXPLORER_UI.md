# CORTEX Studio — Trace Explorer UI

## Access

Open `/studio/ui` on the same origin as the CORTEX API. The page is a
static, dependency-free HTML interface served by FastAPI; it does not add a
JavaScript framework, external CDN, or frontend build pipeline.

## Capabilities

- Query the authenticated `GET /studio/traces` endpoint.
- Select a lookback window (1 hour, 24 hours, 3 days, or 7 days) and result
  limit (25–200).
- Browse trace summaries and inspect a chronological span timeline.
- View service, operation name, timestamps, duration, span count, and status.

## Authentication and data handling

The user enters the existing `API_ACCESS_TOKEN` in the page. The browser sends
it as `X-API-Key` for trace API requests. The page does not persist the key
in local or session storage; it remains only in the current document field
until the page is closed or refreshed. Use HTTPS whenever the UI is accessed
outside a trusted local development environment.

The UI consumes only the allowlisted fields returned by the trace API. It
does not request or render span attributes, events, prompts, document content,
or arbitrary payloads. Dynamic trace values are inserted as text, not parsed
as HTML. The static page itself is served without API authentication so that
the browser can load it; all trace data endpoints remain protected by the
existing API-key dependency.

## Route and scope

- UI: `GET /studio/ui` (static page; no trace data returned).
- List: `GET /studio/traces` (API key required).
- Detail: `GET /studio/traces/{trace_id}` (API key required).

This is the first custom Studio surface for trace inspection. It is not yet a
LangGraph graph editor, run replay interface, evaluation workbench, or
multi-tenant authorization layer.
