import hashlib
from io import BytesIO

from openai import OpenAI
from pypdf import PdfReader

from app.chunking import split_text
from app.config import settings
from app.db import connect

client = OpenAI(
    api_key=settings.openai_api_key,
    timeout=settings.openai_timeout_seconds,
    max_retries=settings.openai_max_retries,
)


def extract_text(filename: str, data: bytes) -> str:
    if filename.lower().endswith(".pdf"):
        reader = PdfReader(BytesIO(data))
        return "\n".join(page.extract_text() or "" for page in reader.pages).strip()
    if filename.lower().endswith(".txt"):
        return data.decode("utf-8-sig").strip()
    raise ValueError("Formato não suportado. Envie PDF ou TXT.")


def embed(texts: list[str]) -> list[list[float]]:
    response = client.embeddings.create(
        model=settings.embedding_model,
        input=texts,
        dimensions=settings.embedding_dimensions,
    )
    return [item.embedding for item in response.data]


def ingest(filename: str, data: bytes) -> dict:
    text = extract_text(filename, data)
    chunks = split_text(text, settings.chunk_size, settings.chunk_overlap)
    if not chunks:
        raise ValueError("Nenhum texto extraível foi encontrado no arquivo.")

    digest = hashlib.sha256(data).hexdigest()
    with connect() as conn:
        existing = conn.execute(
            "SELECT id FROM rag_documents WHERE content_sha256 = %s", (digest,)
        ).fetchone()
    if existing:
        return {"document_id": existing[0], "chunks": 0, "status": "already_exists"}

    vectors = embed(chunks)
    with connect() as conn:
        doc = conn.execute(
            """INSERT INTO rag_documents (filename, content_sha256)
               VALUES (%s, %s)
               ON CONFLICT (content_sha256) DO NOTHING
               RETURNING id""",
            (filename, digest),
        ).fetchone()
        if doc is None:
            existing = conn.execute(
                "SELECT id FROM rag_documents WHERE content_sha256 = %s", (digest,)
            ).fetchone()
            return {"document_id": existing[0], "chunks": 0, "status": "already_exists"}
        document_id = doc[0]
        conn.executemany(
            """INSERT INTO rag_chunks (document_id, chunk_index, content, embedding)
               VALUES (%s, %s, %s, %s)""",
            [
                (document_id, i, chunk, vector)
                for i, (chunk, vector) in enumerate(zip(chunks, vectors))
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
            "grounded": False,
        }

    context = "\n\n".join(
        f"[Fonte: {filename} | similaridade: {score:.3f}]\n{content}"
        for filename, content, score in rows
    )
    completion = client.chat.completions.create(
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
    )
    return {
        "answer": completion.choices[0].message.content or "",
        "sources": [
            {"filename": row[0], "similarity": round(float(row[2]), 4)}
            for row in rows
        ],
        "grounded": True,
    }
