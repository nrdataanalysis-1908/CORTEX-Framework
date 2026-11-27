import hashlib
import json
import re

from openai import OpenAI

from app.chunking import split_text
from app.config import settings
from app.db import connect
from app.observability import (
    record_permanent_failure,
    record_retry_attempt,
    record_retry_exhausted,
    record_retry_recovered,
)
from app.pdf_isolation import extract_validated_text_isolated
from evaluation.groundedness import validate_groundedness_result
from app.resilience import (
    is_retryable_openai_error,
    BulkheadFullError,
    retry_call,
    upstream_circuit_breaker,
    embedding_bulkhead,
    chat_bulkhead,
)

_CITATION_RE = re.compile(r"\[E([1-9][0-9]*)\]")
MIN_EVIDENCE_SIMILARITY = 0.25

# Application-level retry policy owns retries; disable hidden SDK retries to
# prevent multiplicative attempts and make retry telemetry deterministic.
client = OpenAI(
    api_key=settings.openai_api_key,
    timeout=settings.openai_timeout_seconds,
    max_retries=0,
)


def _call_openai(operation: str, call):
    bulkhead = embedding_bulkhead if operation.startswith("embeddings.") else chat_bulkhead

    def execute_attempt():
        # Acquire capacity only for the network attempt, never during retry backoff.
        return bulkhead.call(call)

    def execute_with_retry():
        return retry_call(
            operation,
            execute_attempt,
            max_retries=settings.openai_max_retries,
            base_delay_seconds=settings.openai_retry_base_delay_seconds,
            max_delay_seconds=settings.openai_retry_max_delay_seconds,
            is_retryable=is_retryable_openai_error,
            on_retry=record_retry_attempt,
            on_recovered=record_retry_recovered,
            on_exhausted=record_retry_exhausted,
            on_permanent_failure=record_permanent_failure,
        )

    return upstream_circuit_breaker.call(
        execute_with_retry,
        is_failure=is_retryable_openai_error,
        is_ignored=lambda error: isinstance(error, BulkheadFullError),
    )


def extract_text(filename: str, data: bytes, content_type: str | None = None) -> str:
    text, _ = extract_validated_text_isolated(filename, data, content_type)
    return text


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


def ingest(filename: str, data: bytes, content_type: str | None = None) -> dict:
    text, safe_filename = extract_validated_text_isolated(filename, data, content_type)
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
            (safe_filename, digest),
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


def _citation_metadata(answer: str, evidence_ids: set[str]) -> dict:
    """Validate citation tokens against evidence IDs actually supplied to the model."""
    mentioned = list(dict.fromkeys(f"E{match}" for match in _CITATION_RE.findall(answer)))
    valid = [item for item in mentioned if item in evidence_ids]
    invalid = [item for item in mentioned if item not in evidence_ids]

    if invalid:
        status = "invalid_citation_reference"
    elif valid:
        status = "retrieved_cited_not_verified"
    else:
        status = "retrieved_not_cited"

    return {
        "citation_ids": valid,
        "unresolved_citation_ids": invalid,
        "evidence_status": status,
    }



def _evaluate_groundedness(answer: str, evidence: list[dict]) -> dict:
    """Ask a separate judge to assess each atomic answer claim against evidence."""
    evidence_ids = {item["evidence_id"] for item in evidence}
    evidence_context = "\n\n".join(
        f"[{item['evidence_id']}] {item['text']}" for item in evidence
    )
    try:
        completion = _call_openai(
            "chat.completions.groundedness",
            lambda: client.chat.completions.create(
                model=settings.chat_model,
                temperature=0,
                response_format={"type": "json_object"},
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Você é um avaliador de groundedness de respostas RAG. "
                            "Decomponha a resposta em afirmações atômicas verificáveis. "
                            "Para cada afirmação, compare estritamente o conteúdo com as "
                            "evidências fornecidas. Use somente estes veredictos: "
                            "supported (evidência sustenta integralmente), "
                            "unsupported (não há suporte), contradicted (evidência contradiz), "
                            "unverifiable (não é possível decidir). Não use conhecimento externo. "
                            "Não considere uma citação como prova por si só. Inclua evidence_ids "
                            "somente quando a resposta associar explicitamente a afirmação à "
                            "evidência correspondente. Retorne JSON com a forma: "
                            '{"claims":[{"claim":"...","status":"supported|unsupported|'
                            'contradicted|unverifiable","evidence_ids":["E1"],'
                            '"rationale":"..."}]}. Se não houver afirmações verificáveis, '
                            "retorne claims vazio."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"RESPOSTA:\n{answer}\n\n"
                            f"EVIDÊNCIAS DISPONÍVEIS:\n{evidence_context}"
                        ),
                    },
                ],
            ),
        )
        raw = completion.choices[0].message.content or ""
        result = validate_groundedness_result(json.loads(raw), evidence_ids)
        return {
            "groundedness": result["status"],
            "groundedness_claims": result["claims"],
            "groundedness_summary": result["claim_status_counts"],
            "groundedness_method": result["evaluation_method"],
            "groundedness_disclaimer": result["disclaimer"],
        }
    except Exception as exc:
        # Evaluation is advisory: judge/provider/format failures must not fail /ask.
        return {
            "groundedness": "evaluation_error",
            "groundedness_claims": [],
            "groundedness_summary": {
                "total": 0,
                "supported": 0,
                "unsupported": 0,
                "contradicted": 0,
                "unverifiable": 0,
                "invalid_citation_reference": 0,
            },
            "groundedness_error": type(exc).__name__,
        }


def answer_question(question: str) -> dict:
    query_vector = embed([question])[0]
    with connect() as conn:
        rows = conn.execute(
            """SELECT d.id, c.id, d.filename, c.chunk_index, c.content,
                      1 - (c.embedding <=> %s) AS similarity
               FROM rag_chunks c
               JOIN rag_documents d ON d.id = c.document_id
               ORDER BY c.embedding <=> %s
               LIMIT %s""",
            (query_vector, query_vector, settings.top_k),
        ).fetchall()

    if not rows or rows[0][5] < MIN_EVIDENCE_SIMILARITY:
        return {
            "answer": "Não encontrei evidências suficientes nos documentos disponíveis.",
            "sources": [],
            "evidence": [],
            "citation_ids": [],
            "unresolved_citation_ids": [],
            "evidence_retrieved": False,
            "evidence_status": "insufficient",
            "groundedness": "not_evaluated",
            "groundedness_claims": [],
            "groundedness_summary": {"supported": 0, "unsupported": 0, "contradicted": 0, "unverifiable": 0},
            "groundedness_method": "llm_judge",\n            "groundedness_disclaimer": "No evidence was retrieved; claim evaluation was not run.",
        }

    evidence = [
        {
            "evidence_id": f"E{index}",
            "document_id": row[0],
            "chunk_id": row[1],
            "filename": row[2],
            "chunk_index": row[3],
            "similarity": round(float(row[5]), 4),
            "text": row[4],
        }
        for index, row in enumerate(rows, start=1)
    ]
    evidence_ids = {item["evidence_id"] for item in evidence}
    context = "\n\n".join(
        f"[{item['evidence_id']} | documento: {item['filename']} | "
        f"document_id: {item['document_id']} | chunk_id: {item['chunk_id']} | "
        f"chunk_index: {item['chunk_index']} | similaridade: {item['similarity']:.3f}]\n"
        f"{item['text']}"
        for item in evidence
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
                        "Responda em português usando somente as evidências fornecidas. "
                        "Toda afirmação factual baseada no contexto deve citar o identificador "
                        "correspondente no formato [E1]. Não invente nem altere identificadores. "
                        "Se as evidências não sustentarem a resposta, declare que não há "
                        "evidência suficiente. Uma citação identifica a origem do trecho, "
                        "mas não prova por si só que a afirmação está correta."
                    ),
                },
                {
                    "role": "user",
                    "content": f"EVIDÊNCIAS:\n{context}\n\nPERGUNTA:\n{question}",
                },
            ],
        ),
    )
    answer = completion.choices[0].message.content or ""
    citation_metadata = _citation_metadata(answer, evidence_ids)
    groundedness_metadata = _evaluate_groundedness(answer, evidence)
    return {
        "answer": answer,
        "sources": [
            {"filename": item["filename"], "similarity": item["similarity"]}
            for item in evidence
        ],
        "evidence": evidence,
        **citation_metadata,
        **groundedness_metadata,
        "evidence_retrieved": True,
    }
