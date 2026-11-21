import hashlib
from io import BytesIO

from openai import OpenAI
from pypdf import PdfReader

from app.chunking import split_text
from app.config import settings
from app.db import connect
from app.observability import (
    record_permanent_failure,
    record_retry_attempt,
    record_retry_exhausted,
    record_retry_recovered,
)
from app.resilience import is_retryable_openai_error, retry_call

# Application-level retry policy owns retries; disable hidden SDK retries to
# prevent multiplicative attempts and make retry telemetry deterministic.
client = OpenAI(
    api_key=settings.openai_api_key,
    timeout=settings.openai_timeout_seconds,
    max_retries=0,
)


def _call_openai(operation: str, call):
    return retry_call(
        operation,
        call,
        max_retries=settings.openai_max_retries,
        base_delay_seconds=settings.openai_retry_base_delay_seconds,
        max_delay_seconds=settings.openai_retry_max_delay_seconds,
        is_retryable=is_retryable_openai_error,
        on_retry=record_retry_attempt,
        on_recovered=record_retry_recovered,
        on_exhausted=record_retry_exhausted,
        on_permanent_failure=record_permanent_failure,
    )


def extract_text(filename: str, data: bytes) -> str:
    if filename.lower().endswith(".pdf"):
        reader = PdfReader(BytesIO(data))
        return "\n".join(page.extract_text() or "" for page in reader.pages).strip()
    if filename.lower().endswith(".txt"):
        return data.decode("utf-8-sig").strip()
    raise ValueError("Formato não suportado. Envie PDF ou TXT.")


def embed(texts: list[str]) -> list[list[float]]:
    response = _call_openai(
        "embeddings.create",
        lambda: client.embeddings.create(
            model=settings.embedding_model,
            input=texts,
            dimensions=settings.embedding_dimensions,
        ),
    )
    return [item.embedding for item in response.data]


def ingest(filename: str, data: bytes) -> dict:
    text = extract_text(filename, data)
    chunks = split_text(text, settings.chunk_size, settings.chunk_overlap)
    if not chunks:
        raise ValueError("Nenhum texto extraível foi encontrado no arquivo.")

    digest = hashlib.sha256(data).hexdigest()
    # Serialize identical payloads across API workers/processes. The transaction-scoped
    # advisory lock is released automatically on commit or rollback.
    with connect() as conn:
        conn.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
            (digest,),
        )
        existing = conn.execute(
            "SELECT id FROM rag_documents WHERE content_sha256 = %s", (digest,)
        ).fetchone()
        if existing:
            return {"document_id": existing[0], "chunks": 0, "status": "already_exists"}

        # Keep the per-digest lock until both document metadata and all chunks commit.
        # This prevents concurrent requests from generating duplicate embeddings.
        vectors = embed(chunks)
        if len(vectors) != len(chunks):
            raise RuntimeError("A quantidade de embeddings difere da quantidade de chunks.")

        doc = conn.execute(
            """INSERT INTO rag_documents (filename, content_sha256)
               VALUES (%s, %s)
               RETURNING id""",
            (filename, digest),
        ).fetchone()
        document_id = doc[0]
        with conn.cursor() as cursor:
            cursor.executemany(
                """INSERT INTO rag_chunks (document_id, chunk_index, content, embedding)
                   VALUES (%s, %s, %s, %s)""",
                [
                    (document_id, i, chunk, vector)
                    for i, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True))
                ],
            )
    return {"document_id": document_id, "chunks": len(chunks), "status": "ingested"}


def answer_question(question: str) -> dict:
    query_vector = embed([question])[0]
    with connect() as conn:
        rows = conn.execute(
            """SELECT d.filename, c.content,
                      1 - (c.embedding <=> %s) AS similarity
               FROM rag_chunks c
               JOIN rag_documents d ON d.id = c.document_id
               ORDER BY c.embedding <=> %s
               LIMIT %s""",
            (query_vector, query_vector, settings.top_k),
        ).fetchall()

    if not rows or rows[0][2] < 0.25:
        return {
            "answer": "Não encontrei evidências suficientes nos documentos disponíveis.",
            "sources": [],
            "evidence_retrieved": False,
            "groundedness": "not_evaluated",
        }

    context = "\n\n".join(
        f"[Fonte: {filename} | similaridade: {score:.3f}]\n{content}"
        for filename, content, score in rows
    )
    completion = _call_openai(
        "chat.completions.create",
        lambda: client.chat.completions.create(
            model=settings.chat_model,
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Responda em português usando somente o contexto fornecido. "
                        "Se o contexto não sustentar a resposta, declare que não há evidência suficiente. "
                        "Não invente fatos. Cite os nomes dos arquivos usados."
                    ),
                },
                {
                    "role": "user",
                    "content": f"CONTEXTO:\n{context}\n\nPERGUNTA:\n{question}",
                },
            ],
        ),
    )
    return {
        "answer": completion.choices[0].message.content or "",
        "sources": [
            {"filename": row[0], "similarity": round(float(row[2]), 4)}
            for row in rows
        ],
        "evidence_retrieved": True,
        "groundedness": "not_evaluated",
    }
