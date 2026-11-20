import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor

os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/cortex")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-placeholder")

from app import rag
from app.db import connect, init_db


def test_concurrent_ingestion_of_same_content_creates_one_document_and_one_embedding(monkeypatch):
    init_db()
    with connect() as conn:
        conn.execute("TRUNCATE TABLE rag_chunks, rag_documents RESTART IDENTITY CASCADE")

    calls = 0
    calls_lock = threading.Lock()

    def fake_embed(chunks):
        nonlocal calls
        with calls_lock:
            calls += 1
        # Keep the first request inside the transaction long enough for peers to contend.
        time.sleep(0.15)
        return [[0.0] * rag.settings.embedding_dimensions for _ in chunks]

    monkeypatch.setattr(rag, "embed", fake_embed)
    payload = b"Conteudo operacional para validar idempotencia concorrente."

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(
            lambda _: rag.ingest("same-document.txt", payload),
            range(8),
        ))

    assert calls == 1
    assert sum(result["status"] == "ingested" for result in results) == 1
    assert sum(result["status"] == "already_exists" for result in results) == 7
    assert len({result["document_id"] for result in results}) == 1

    with connect() as conn:
        document_count = conn.execute(
            "SELECT COUNT(*) FROM rag_documents"
        ).fetchone()[0]
        chunk_count = conn.execute(
            "SELECT COUNT(*) FROM rag_chunks"
        ).fetchone()[0]

    assert document_count == 1
    assert chunk_count == 1

    with connect() as conn:
        conn.execute("TRUNCATE TABLE rag_chunks, rag_documents RESTART IDENTITY CASCADE")
