from __future__ import annotations

from scripts.summarize_retrieval_report import build_summary


def test_retrieval_summary_reports_deltas_and_ties_without_case_payloads():
    report = {
        "number_of_cases": 20,
        "k": 5,
        "strategies": {
            "dense": {
                "aggregate": {
                    "mrr": 0.70,
                    "recall@1": 0.60,
                    "recall@3": 0.80,
                    "recall@5": 0.90,
                    "ndcg@1": 0.60,
                    "ndcg@3": 0.75,
                    "ndcg@5": 0.82,
                },
                "cases": [{"query": "private-ish benchmark text"}],
            },
            "hybrid": {
                "aggregate": {
                    "mrr": 0.75,
                    "recall@1": 0.65,
                    "recall@3": 0.85,
                    "recall@5": 0.95,
                    "ndcg@1": 0.65,
                    "ndcg@3": 0.80,
                    "ndcg@5": 0.87,
                }
            },
            "hybrid_rerank": {
                "aggregate": {
                    "mrr": 0.80,
                    "recall@1": 0.70,
                    "recall@3": 0.90,
                    "recall@5": 0.95,
                    "ndcg@1": 0.70,
                    "ndcg@3": 0.85,
                    "ndcg@5": 0.90,
                }
            },
        },
    }

    summary = build_summary(report)

    assert summary["number_of_cases"] == 20
    assert summary["best_by_metric"]["mrr"] == "hybrid_rerank"
    assert summary["ties_by_metric"]["recall@5"] == ["hybrid", "hybrid_rerank"]
    assert abs(summary["delta_vs_dense"]["hybrid_rerank"]["mrr"] - 0.10) < 1e-12
    assert abs(summary["delta_vs_dense"]["hybrid_rerank"]["recall@5"] - 0.05) < 1e-12
    assert "cases" not in summary
    assert "private-ish benchmark text" not in str(summary)
