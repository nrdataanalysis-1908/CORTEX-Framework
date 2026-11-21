import hashlib
import os

import psycopg
import pytest

os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/cortex")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-placeholder")

from app import rag
from app.db import connect, init_db


def _document_counts(digest: str) -> tuple[int, int]:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT COUNT(DISTINCT d.id), COUNT(c.id)
            FROM rag_documents d
            LEFT JOIN rag_chunks c ON c.document_id = d.id
            WHERE d.content_sha256 = %s
            """,
            (digest,),
        ).fetchone()
    return row[0], row[1]


def _fake_embeddings(chunks: list[str]) -> list[list[float]]:
    return [[0.0] * rag.settings.embedding_dimensions for _ in chunks]


def test_embedding_failure_leaves_no_partial_document_and_retry_succeeds(monkeypatch):
    init_db()
    payload = b"CORTEX embedding provider failure must be retryable."
    digest = hashlib.sha256(payload).hexdigest()

    def fail_embedding(_chunks):
        raise RuntimeError("simulated embedding provider outage")

    monkeypatch.setattr(rag, "embed", fail_embedding)

    with pytest.raises(RuntimeError, match="simulated embedding provider outage"):
        rag.ingest("embedding-retry.txt", payload)

    assert _document_counts(digest) == (0, 0)

    monkeypatch.setattr(rag, "embed", _fake_embeddings)
    result = rag.ingest("embedding-retry.txt", payload)

    assert result["status"] == "ingested"
    assert _document_counts(digest) == (1, 1)


def test_chunk_insert_failure_rolls_back_document_and_retry_succeeds(monkeypatch):
    init_db()
    payload = b"CORTEX_ATOMICITY_DB_FAILURE_MARKER forces a database chunk insert failure."
    digest = hashlib.sha256(payload).hexdigest()

    with connect() as conn:
        conn.execute(
            """
            CREATE OR REPLACE FUNCTION public.cortex_test_fail_chunk_insert()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
                IF NEW.content LIKE '%CORTEX_ATOMICITY_DB_FAILURE_MARKER%' THEN
                    RAISE EXCEPTION 'simulated chunk persistence failure';
                END IF;
                RETURN NEW;
            END;
            $$
            """
        )
        conn.execute(
            """
            CREATE TRIGGER cortex_test_fail_chunk_insert
            BEFORE INSERT ON public.rag_chunks
            FOR EACH ROW
            EXECUTE FUNCTION public.cortex_test_fail_chunk_insert()
            """
        )

    monkeypatch.setattr(rag, "embed", _fake_embeddings)
    try:
        with pytest.raises(psycopg.Error, match="simulated chunk persistence failure"):
            rag.ingest("database-retry.txt", payload)

        # The document row and every chunk must roll back as one unit.
        assert _document_counts(digest) == (0, 0)
    finally:
        with connect() as conn:
            conn.execute(
                "DROP TRIGGER IF EXISTS cortex_test_fail_chunk_insert ON public.rag_chunks"
            )
            conn.execute(
                "DROP FUNCTION IF EXISTS public.cortex_test_fail_chunk_insert()"
            )

    result = rag.ingest("database-retry.txt", payload)

    assert result["status"] == "ingested"
    assert _document_counts(digest) == (1, 1)
