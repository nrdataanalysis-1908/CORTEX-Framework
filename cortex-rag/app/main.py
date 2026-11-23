import json
import logging
import math
import uuid
from contextlib import asynccontextmanager
from time import perf_counter

import psycopg
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi import Depends
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from app.db import check_database, init_db
from app.observability import metrics_snapshot, record_request
from app.rag import answer_question, ingest
from app.rate_limit import enforce_api_rate_limit
from app.request_limits import RequestBodyLimitMiddleware
from app.resilience import BulkheadFullError, CircuitOpenError
from app.pdf_isolation import PdfWorkerExecutionError, PdfWorkerTimeoutError
from app.tracing import configure_tracing
from app.cortex_studio import router as cortex_studio_router

MAX_UPLOAD_BYTES = 15 * 1024 * 1024
# Allow bounded multipart framing/metadata in addition to the 15 MiB file payload.
MAX_REQUEST_BODY_BYTES = MAX_UPLOAD_BYTES + 1024 * 1024

logger = logging.getLogger("cortex.startup")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in ("method", "path", "status_code", "duration_ms", "request_id"):
            if hasattr(record, field):
                payload[field] = getattr(record, field)
        return json.dumps(payload, ensure_ascii=False)


_handler = logging.StreamHandler()
_handler.setFormatter(JsonFormatter())
logging.basicConfig(level=logging.INFO, handlers=[_handler], force=True)


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        init_db()
    except psycopg.Error:
        # Keep the process alive so liveness remains observable during DB outages.
        logger.exception("database_initialization_failed")
    yield


app = FastAPI(
    title="CORTEX RAG API",
    description="RAG documental com FastAPI, PostgreSQL e pgvector.",
    version="0.5.0",
    lifespan=lifespan,
)
app.add_middleware(
    RequestBodyLimitMiddleware,
    max_body_bytes=MAX_REQUEST_BODY_BYTES,
    protected_path="/documents",
)
configure_tracing(app)
app.include_router(cortex_studio_router)


def _resolve_request_id(candidate: str | None) -> str:
    """Accept only short printable ASCII request IDs; replace unsafe values."""
    if (
        candidate
        and len(candidate) <= 128
        and all(0x21 <= ord(char) <= 0x7E for char in candidate)
    ):
        return candidate
    return str(uuid.uuid4())


@app.middleware("http")
async def request_observability(request: Request, call_next):
    request_id = _resolve_request_id(request.headers.get("X-Request-ID"))
    started = perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
    except Exception:
        record_request(
            request.method, request.url.path, status_code,
            (perf_counter() - started) * 1000, request_id,
        )
        raise
    duration_ms = (perf_counter() - started) * 1000
    record_request(request.method, request.url.path, status_code, duration_ms, request_id)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time-Ms"] = f"{duration_ms:.3f}"
    return response


class QuestionRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)


def _circuit_open_http_exception(exc: CircuitOpenError) -> HTTPException:
    retry_after = max(1, math.ceil(exc.retry_after_seconds))
    return HTTPException(
        status_code=503,
        detail="Provedor temporariamente indisponível; circuito de proteção aberto.",
        headers={"Retry-After": str(retry_after)},
    )


def _bulkhead_full_http_exception(exc: BulkheadFullError) -> HTTPException:
    retry_after = max(1, math.ceil(exc.retry_after_seconds))
    return HTTPException(
        status_code=503,
        detail=f"Capacidade concorrente esgotada para a operação {exc.operation}.",
        headers={"Retry-After": str(retry_after)},
    )


@app.get("/health")
def health():
    return {"status": "ok", "service": "cortex-rag", "check": "liveness"}


@app.get("/ready")
def readiness():
    if not check_database():
        raise HTTPException(status_code=503, detail="Banco de dados indisponível ou esquema não inicializado.")
    return {"status": "ready", "database": "available"}


@app.get("/metrics", dependencies=[Depends(enforce_api_rate_limit)])
def metrics():
    return JSONResponse(metrics_snapshot())



async def _read_upload_limited(file: UploadFile) -> bytes:
    """Reject known oversized multipart files before allocating their contents."""
    if file.size is not None and file.size > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Arquivo excede o limite de 15 MB.")

    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Arquivo excede o limite de 15 MB.")
    return data


@app.post("/documents", status_code=201, dependencies=[Depends(enforce_api_rate_limit)])
async def upload_document(file: UploadFile = File(...)):
    try:
        data = await _read_upload_limited(file)
        return await run_in_threadpool(ingest, file.filename or "", data, file.content_type)
    except CircuitOpenError as exc:
        raise _circuit_open_http_exception(exc) from exc
    except BulkheadFullError as exc:
        raise _bulkhead_full_http_exception(exc) from exc
    except PdfWorkerTimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except PdfWorkerExecutionError as exc:
        raise HTTPException(status_code=503, detail="Worker de extração PDF indisponível ou sem isolamento.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/ask", dependencies=[Depends(enforce_api_rate_limit)])
def ask(payload: QuestionRequest):
    try:
        return answer_question(payload.question)
    except CircuitOpenError as exc:
        raise _circuit_open_http_exception(exc) from exc
    except BulkheadFullError as exc:
        raise _bulkhead_full_http_exception(exc) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Falha ao processar a consulta RAG.") from exc
