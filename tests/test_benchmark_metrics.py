from __future__ import annotations

import pytest

from app.evaluation import (
    evaluate_grounding_labels,
    evaluate_retrieval_ranking,
    ndcg_at_k,
    recall_at_k,
    reciprocal_rank,
)


def test_retrieval_metrics_rank_relevant_items() -> None:
    ranked = ["noise", "relevant_a", "relevant_b"]
    relevant = ["relevant_a", "relevant_b"]

    assert recall_at_k(ranked, relevant, 1) == 0.0
    assert recall_at_k(ranked, relevant, 3) == 1.0
    assert reciprocal_rank(ranked, relevant) == 0.5
    assert 0.0 < ndcg_at_k(ranked, relevant, 3) < 1.0

    metrics = evaluate_retrieval_ranking(ranked, relevant)
    assert metrics["recall@3"] == 1.0
    assert metrics["mrr"] == 0.5


def test_retrieval_metrics_validate_k() -> None:
    with pytest.raises(ValueError):
        recall_at_k(["a"], ["a"], 0)
    with pytest.raises(ValueError):
        ndcg_at_k(["a"], ["a"], 0)


def test_grounding_metrics_perfect_predictions() -> None:
    labels = ["supported", "unsupported", "ambiguous"]
    result = evaluate_grounding_labels(labels, labels)

    assert result["accuracy"] == 1.0
    assert result["macro_f1"] == 1.0
    assert result["expected_distribution"] == {
        "supported": 1,
        "unsupported": 1,
        "ambiguous": 1,
    }


def test_grounding_metrics_reject_invalid_labels() -> None:
    with pytest.raises(ValueError):
        evaluate_grounding_labels(["invented"], ["supported"])
