import psycopg
from pgvector.psycopg import register_vector

from app.config import settings


def connect():
    conn = psycopg.connect(
        settings.database_url,
        connect_timeout=settings.database_connect_timeout_seconds,
    )
    register_vector(conn)
    return conn


def check_database() -> bool:
    """Return True only when PostgreSQL is reachable and the RAG schema exists."""
    try:
        with connect() as conn:
            row = conn.execute(
                """SELECT
                       to_regclass('public.rag_documents') IS NOT NULL
                       AND to_regclass('public.rag_chunks') IS NOT NULL
                       AND to_regclass('public.api_rate_limits') IS NOT NULL"""
            ).fetchone()
        return bool(row and row[0])
    except psycopg.Error:
        return False


def init_db():
    # The pgvector type must exist before register_vector() inspects the connection.
    # Bootstrap the extension with a plain psycopg connection on fresh databases.
    with psycopg.connect(
        settings.database_url,
        connect_timeout=settings.database_connect_timeout_seconds,
    ) as conn:
        conn.execute("CREATE EXTENSION IF NOT EXISTS vector")

    with connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS rag_documents (
                id BIGSERIAL PRIMARY KEY,
                filename TEXT NOT NULL,
                content_sha256 TEXT NOT NULL UNIQUE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS rag_chunks (
                id BIGSERIAL PRIMARY KEY,
                document_id BIGINT NOT NULL REFERENCES rag_documents(id) ON DELETE CASCADE,
                chunk_index INTEGER NOT NULL,
                content TEXT NOT NULL,
                embedding VECTOR({settings.embedding_dimensions}) NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE(document_id, chunk_index)
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS rag_chunks_embedding_hnsw
            ON rag_chunks USING hnsw (embedding vector_cosine_ops)
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS api_rate_limits (
                key_hash CHAR(64) PRIMARY KEY,
                window_start TIMESTAMPTZ NOT NULL,
                request_count INTEGER NOT NULL CHECK (request_count >= 1)
            )
        """)
