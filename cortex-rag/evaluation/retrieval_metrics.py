"""Ranking metrics for evidence retrieval, using binary gold-evidence relevance."""
from __future__ import annotations

import math


def reciprocal_rank(relevance: list[bool]) -> float:
    """Reciprocal rank of the first relevant result; zero when none is relevant."""
    for rank, relevant in enumerate(relevance, start=1):
        if relevant:
            return 1.0 / rank
    return 0.0


def discounted_cumulative_gain(relevance: list[bool]) -> float:
    """DCG with binary relevance and logarithmic rank discount."""
    return sum(1.0 / math.log2(rank + 1) for rank, relevant in enumerate(relevance, start=1) if relevant)


def normalized_dcg(relevance: list[bool]) -> float:
    """NDCG@K; ideal ranking places all retrieved relevant items first."""
    ideal = discounted_cumulative_gain(sorted(relevance, reverse=True))
    if ideal == 0:
        return 0.0
    return discounted_cumulative_gain(relevance) / ideal


def ranking_summary(rankings: list[list[bool]]) -> dict:
    """Aggregate Recall@K, MRR@K, and NDCG@K over query-level ranked relevance."""
    if not rankings:
        return {"queries": 0, "recall": 0.0, "mrr": 0.0, "ndcg": 0.0}
    reciprocal_ranks = [reciprocal_rank(ranking) for ranking in rankings]
    ndcgs = [normalized_dcg(ranking) for ranking in rankings]
    recalls = [any(ranking) for ranking in rankings]
    count = len(rankings)
    return {
        "queries": count,
        "recall": round(sum(recalls) / count, 4),
        "mrr": round(sum(reciprocal_ranks) / count, 4),
        "ndcg": round(sum(ndcgs) / count, 4),
    }
