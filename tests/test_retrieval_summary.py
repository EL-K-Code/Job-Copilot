from __future__ import annotations

from scripts.summarize_retrieval_report import build_summary


def test_retrieval_summary_reports_deltas_ties_and_latency_without_case_payloads():
    report = {
        "number_of_cases": 20,
        "k": 5,
        "latency_scope": "warm_process",
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
                    "mean_latency_ms": 10.0,
                    "p50_latency_ms": 9.0,
                    "p95_latency_ms": 15.0,
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
                    "mean_latency_ms": 14.0,
                    "p50_latency_ms": 13.0,
                    "p95_latency_ms": 20.0,
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
                    "mean_latency_ms": 32.0,
                    "p50_latency_ms": 30.0,
                    "p95_latency_ms": 45.0,
                }
            },
        },
    }

    summary = build_summary(report)

    assert summary["number_of_cases"] == 20
    assert summary["latency_scope"] == "warm_process"
    assert summary["best_by_metric"]["mrr"] == "hybrid_rerank"
    assert summary["best_by_metric"]["mean_latency_ms"] == "dense"
    assert summary["ties_by_metric"]["recall@5"] == ["hybrid", "hybrid_rerank"]
    assert abs(summary["delta_vs_dense"]["hybrid_rerank"]["mrr"] - 0.10) < 1e-12
    assert abs(summary["delta_vs_dense"]["hybrid_rerank"]["recall@5"] - 0.05) < 1e-12
    assert summary["delta_vs_dense"]["hybrid_rerank"]["mean_latency_ms"] == 22.0
    assert summary["delta_vs_dense"]["hybrid_rerank"]["p95_latency_ms"] == 30.0
    assert "cases" not in summary
    assert "private-ish benchmark text" not in str(summary)
