import logging
import uuid
from contextlib import asynccontextmanager
from time import perf_counter

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.db import check_database, init_db
from app.observability import metrics_snapshot, record_request
from app.rag import answer_question, ingest

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="CORTEX RAG API",
    description="RAG documental com FastAPI, PostgreSQL e pgvector.",
    version="0.2.0",
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


@app.get("/health")
def health():
    return {"status": "ok", "service": "cortex-rag", "check": "liveness"}


@app.get("/ready")
def readiness():
    if not check_database():
        raise HTTPException(status_code=503, detail="Banco de dados indisponível.")
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
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/ask")
def ask(payload: QuestionRequest):
    try:
        return answer_question(payload.question)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Falha ao processar a consulta RAG.") from exc
