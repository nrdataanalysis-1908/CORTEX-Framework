"""Retrieval evaluation against the synthetic gold set.

Run from cortex-rag after ingesting evaluation/fixtures/manual_operacional_sintetico.txt:
    python -m evaluation.run_eval --k 5
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.config import settings
from app.db import connect
from app.rag import embed
from evaluation.retrieval_metrics import ranking_summary

ROOT = Path(__file__).resolve().parent
CASES = ROOT / "questions.json"


def evaluate(k: int) -> dict:
    if k < 1:
        raise ValueError("k must be greater than zero")
    cases = json.loads(CASES.read_text(encoding="utf-8"))
    vectors = embed([case["question"] for case in cases])
    rankings = []
    details = []

    with connect() as conn:
        for case, vector in zip(cases, vectors, strict=True):
            rows = conn.execute(
                """SELECT c.content, d.filename,
                          1 - (c.embedding <=> %s) AS similarity
                   FROM rag_chunks c
                   JOIN rag_documents d ON d.id = c.document_id
                   ORDER BY c.embedding <=> %s
                   LIMIT %s""",
                (vector, vector, k),
            ).fetchall()
            evidence = case["expected_evidence"].casefold()
            relevance = [evidence in row[0].casefold() for row in rows]
            rankings.append(relevance)
            relevant_ranks = [rank for rank, is_relevant in enumerate(relevance, start=1) if is_relevant]
            details.append({
                "id": case["id"],
                "hit": any(relevance),
                "relevant_ranks": relevant_ranks,
                "expected_evidence": case["expected_evidence"],
                "retrieved_sources": sorted({row[1] for row in rows}),
                "top_similarity": round(float(rows[0][2]), 4) if rows else None,
            })

    metrics = ranking_summary(rankings)
    hits = sum(1 for ranking in rankings if any(ranking))
    return {
        "metric": "binary_gold_evidence_ranking",
        "k": k,
        "cases": len(cases),
        "hits": hits,
        "misses": len(cases) - hits,
        "score": metrics["recall"],
        "metrics": {
            "recall_at_k": metrics["recall"],
            "mrr_at_k": metrics["mrr"],
            "ndcg_at_k": metrics["ndcg"],
        },
        "details": details,
        "interpretation": (
            "Recall@K mede a proporção de consultas com ao menos um chunk contendo "
            "a evidência-ouro. MRR@K recompensa a posição do primeiro chunk relevante; "
            "NDCG@K mede a ordenação dos chunks relevantes. A relevância é binária e "
            "definida por correspondência literal da evidência-ouro. Nenhuma dessas "
            "métricas mede correção factual ou qualidade da resposta gerada."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Avalia recuperação de evidências do CORTEX RAG.")
    parser.add_argument("--k", type=int, default=settings.top_k)
    parser.add_argument("--output", type=Path, default=ROOT / "results" / "latest.json")
    args = parser.parse_args()
    if args.k < 1:
        parser.error("--k deve ser maior que zero.")

    report = evaluate(args.k)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = {
        "metric": report["metric"],
        "k": report["k"],
        "cases": report["cases"],
        "hits": report["hits"],
        "misses": report["misses"],
        **report["metrics"],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Relatório completo: {args.output}")


if __name__ == "__main__":
    main()
