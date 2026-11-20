from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.db import init_db
from app.rag import answer_question, ingest


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="CORTEX RAG API",
    description="RAG documental com FastAPI, PostgreSQL e pgvector.",
    version="0.1.0",
    lifespan=lifespan,
)


class QuestionRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)


@app.get("/health")
def health():
    return {"status": "ok", "service": "cortex-rag"}


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
