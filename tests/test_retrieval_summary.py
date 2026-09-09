from __future__ import annotations

from scripts.summarize_retrieval_report import build_summary


def _case(case_id: str, *, mrr: float, recall5: float, ndcg5: float) -> dict:
    return {
        "id": case_id,
        "metrics": {
            "mrr": mrr,
            "recall@1": recall5,
            "recall@3": recall5,
            "recall@5": recall5,
            "ndcg@1": ndcg5,
            "ndcg@3": ndcg5,
            "ndcg@5": ndcg5,
        },
    }


def test_retrieval_summary_reports_deltas_ties_latency_and_paired_uncertainty():
    report = {
        "number_of_cases": 4,
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
                "cases": [
                    _case("c1", mrr=1.0, recall5=1.0, ndcg5=1.0),
                    _case("c2", mrr=0.5, recall5=1.0, ndcg5=0.8),
                    _case("c3", mrr=0.5, recall5=0.5, ndcg5=0.6),
                    _case("c4", mrr=0.8, recall5=1.0, ndcg5=0.88),
                ],
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
                },
                "cases": [
                    _case("c1", mrr=1.0, recall5=1.0, ndcg5=1.0),
                    _case("c2", mrr=1.0, recall5=1.0, ndcg5=1.0),
                    _case("c3", mrr=0.5, recall5=1.0, ndcg5=0.7),
                    _case("c4", mrr=0.5, recall5=1.0, ndcg5=0.78),
                ],
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
                },
                "cases": [
                    _case("c1", mrr=1.0, recall5=1.0, ndcg5=1.0),
                    _case("c2", mrr=1.0, recall5=1.0, ndcg5=1.0),
                    _case("c3", mrr=0.8, recall5=1.0, ndcg5=0.9),
                    _case("c4", mrr=0.4, recall5=1.0, ndcg5=0.7),
                ],
            },
        },
    }

    summary = build_summary(report)

    assert summary["schema_version"] == 2
    assert summary["number_of_cases"] == 4
    assert summary["latency_scope"] == "warm_process"
    assert summary["best_by_metric"]["mrr"] == "hybrid_rerank"
    assert summary["best_by_metric"]["mean_latency_ms"] == "dense"
    assert summary["ties_by_metric"]["recall@5"] == ["hybrid", "hybrid_rerank"]
    assert abs(summary["delta_vs_dense"]["hybrid_rerank"]["mrr"] - 0.10) < 1e-12
    assert abs(summary["delta_vs_dense"]["hybrid_rerank"]["recall@5"] - 0.05) < 1e-12
    assert summary["delta_vs_dense"]["hybrid_rerank"]["mean_latency_ms"] == 22.0
    assert summary["delta_vs_dense"]["hybrid_rerank"]["p95_latency_ms"] == 30.0

    paired = summary["paired_vs_dense"]["hybrid_rerank"]["mrr"]
    assert paired["paired_cases"] == 4
    assert paired["wins"] == 2
    assert paired["ties"] == 1
    assert paired["losses"] == 1
    assert paired["bootstrap_samples"] == 2000
    assert len(paired["bootstrap_ci95"]) == 2
    assert paired["bootstrap_ci95"][0] <= paired["mean_delta"] <= paired["bootstrap_ci95"][1]

    assert "cases" not in summary
    assert "query" not in str(summary)


def test_retrieval_summary_omits_paired_comparison_when_case_payloads_are_missing():
    report = {
        "number_of_cases": 1,
        "strategies": {
            "dense": {"aggregate": {}},
            "hybrid": {"aggregate": {}},
        },
    }

    summary = build_summary(report)

    assert summary["paired_vs_dense"] == {}
