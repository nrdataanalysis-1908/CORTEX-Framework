import pytest

from evaluation.retrieval_metrics import (
    discounted_cumulative_gain,
    normalized_dcg,
    ranking_summary,
    reciprocal_rank,
)


def test_reciprocal_rank_uses_first_relevant_position():
    assert reciprocal_rank([False, False, True]) == pytest.approx(1 / 3)
    assert reciprocal_rank([False, False]) == 0.0


def test_ndcg_rewards_relevant_results_at_top():
    assert normalized_dcg([True, True, False]) == pytest.approx(1.0)
    assert normalized_dcg([True, False, True]) < 1.0
    assert normalized_dcg([False, True, True]) < normalized_dcg([True, False, True])
    assert normalized_dcg([False, False]) == 0.0


def test_dcg_uses_logarithmic_discount():
    assert discounted_cumulative_gain([True, True]) == pytest.approx(1 + 1 / 1.5849625007)


def test_ranking_summary_aggregates_query_metrics():
    report = ranking_summary([[True, False], [False, True], [False, False]])
    assert report == {
        "queries": 3,
        "recall": pytest.approx(2 / 3, abs=0.0001),
        "mrr": pytest.approx(0.5, abs=0.0001),
        "ndcg": pytest.approx((1 + 1 / 1.5849625007) / 3, abs=0.0001),
    }


def test_ranking_summary_handles_empty_dataset():
    assert ranking_summary([]) == {
        "queries": 0, "recall": 0.0, "mrr": 0.0, "ndcg": 0.0
    }
