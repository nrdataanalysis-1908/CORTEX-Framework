"""Read-only, privacy-filtered trace inspection API for CORTEX Studio."""
from __future__ import annotations

import re
import time
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query

from app.config import settings
from app.security import require_api_key

router = APIRouter(
    prefix="/studio",
    tags=["CORTEX Studio"],
    dependencies=[Depends(require_api_key)],
)

_TRACE_ID_RE = re.compile(r"^[0-9a-fA-F]{32}$")


def _tempo_unavailable() -> HTTPException:
    return HTTPException(
        status_code=503,
        detail="O mecanismo de traces está temporariamente indisponível.",
    )


async def _tempo_get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(
            base_url=settings.cortex_tempo_url.rstrip("/"),
            timeout=settings.cortex_tempo_timeout_seconds,
        ) as client:
            response = await client.get(path, params=params)
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise _tempo_unavailable() from exc
    if not isinstance(payload, dict):
        raise _tempo_unavailable()
    return payload


def _attributes(items: Any) -> dict[str, Any]:
    """Convert OTLP attributes to a small lookup without returning them to clients."""
    if not isinstance(items, list):
        return {}
    result: dict[str, Any] = {}
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("key"), str):
            continue
        value = item.get("value")
        if isinstance(value, dict):
            value = next(iter(value.values()), None)
        result[item["key"]] = value
    return result


def _safe_trace_summary(item: dict[str, Any]) -> dict[str, Any] | None:
    trace_id = item.get("traceID") or item.get("traceId")
    if not isinstance(trace_id, str) or not _TRACE_ID_RE.fullmatch(trace_id):
        return None
    return {
        "trace_id": trace_id,
        "root_service_name": item.get("rootServiceName"),
        "root_trace_name": item.get("rootTraceName"),
        "start_time_unix_nano": item.get("startTimeUnixNano"),
        "duration_ms": item.get("durationMs"),
        "span_count": item.get("spanCount"),
        "status": item.get("status"),
    }


def _flatten_spans(payload: dict[str, Any], trace_id: str) -> list[dict[str, Any]]:
    batches = payload.get("batches", [])
    if not isinstance(batches, list):
        return []
    spans: list[dict[str, Any]] = []
    for batch in batches:
        if not isinstance(batch, dict):
            continue
        resource = _attributes(batch.get("resource", {}).get("attributes", []))
        service_name = resource.get("service.name")
        for scope in batch.get("scopeSpans", batch.get("instrumentationLibrarySpans", [])):
            if not isinstance(scope, dict):
                continue
            for span in scope.get("spans", []):
                if not isinstance(span, dict):
                    continue
                start = span.get("startTimeUnixNano")
                end = span.get("endTimeUnixNano")
                try:
                    duration_ms = max(0.0, (int(end) - int(start)) / 1_000_000)
                except (TypeError, ValueError):
                    duration_ms = None
                status = span.get("status")
                spans.append({
                    "trace_id": trace_id,
                    "span_id": span.get("spanId"),
                    "parent_span_id": span.get("parentSpanId") or None,
                    "name": span.get("name"),
                    "service_name": service_name,
                    "start_time_unix_nano": start,
                    "duration_ms": duration_ms,
                    "status_code": status.get("code") if isinstance(status, dict) else None,
                })
    spans.sort(key=lambda item: int(item["start_time_unix_nano"] or 0))
    return spans


@router.get("/traces")
async def list_traces(
    limit: int = Query(default=50, ge=1, le=200),
    lookback_seconds: int = Query(default=86_400, ge=60, le=604_800),
) -> dict[str, Any]:
    """List recent traces; only allowlisted metadata is returned."""
    end = int(time.time())
    payload = await _tempo_get(
        "/api/search",
        params={"limit": limit, "start": end - lookback_seconds, "end": end},
    )
    items = payload.get("traces", [])
    if not isinstance(items, list):
        raise _tempo_unavailable()
    traces = [
        summary
        for item in items
        if isinstance(item, dict)
        for summary in [_safe_trace_summary(item)]
        if summary is not None
    ]
    return {"traces": traces, "count": len(traces), "lookback_seconds": lookback_seconds}


@router.get("/traces/{trace_id}")
async def get_trace(trace_id: str) -> dict[str, Any]:
    """Return a sanitized span timeline without span attributes or event payloads."""
    if not _TRACE_ID_RE.fullmatch(trace_id):
        raise HTTPException(status_code=422, detail="Identificador de trace inválido.")
    payload = await _tempo_get(f"/api/traces/{trace_id}")
    spans = _flatten_spans(payload, trace_id)
    if not spans:
        raise HTTPException(status_code=404, detail="Trace não encontrado ou sem spans.")
    return {"trace_id": trace_id, "spans": spans, "span_count": len(spans)}
