import json
import logging
import math
import uuid
from contextlib import asynccontextmanager
from time import perf_counter

import psycopg
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.db import check_database, init_db
from app.observability import metrics_snapshot, record_request
from app.rag import answer_question, ingest
from app.resilience import CircuitOpenError

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
    version="0.3.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def request_observability(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
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


@app.get("/health")
def health():
    return {"status": "ok", "service": "cortex-rag", "check": "liveness"}


@app.get("/ready")
def readiness():
    if not check_database():
        raise HTTPException(status_code=503, detail="Banco de dados indisponível ou esquema não inicializado.")
    return {"status": "ready", "database": "available"}


@app.get("/metrics")
def metrics():
    return JSONResponse(metrics_snapshot())


@app.post("/documents", status_code=201)
async def upload_document(file: UploadFile = File(...)):
    try:
        data = await file.read(15 * 1024 * 1024 + 1)
        if len(data) > 15 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Arquivo excede o limite de 15 MB.")
        return ingest(file.filename or "documento", data)
    except CircuitOpenError as exc:
        raise _circuit_open_http_exception(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/ask")
def ask(payload: QuestionRequest):
    try:
        return answer_question(payload.question)
    except CircuitOpenError as exc:
        raise _circuit_open_http_exception(exc) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Falha ao processar a consulta RAG.") from exc
