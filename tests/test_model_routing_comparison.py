from __future__ import annotations

import pytest

from scripts.compare_model_routing_reports import compare_reports


def _report(*, quality: float, cost: float, dataset_sha: str = "same") -> dict:
    return {
        "task": "structured_job_offer_extraction",
        "benchmark_version": "1.0.0",
        "evaluation_protocol_version": "1.3.0",
        "dataset_sha256": dataset_sha,
        "prompt_sha256": "prompt-same",
        "aggregate": {
            "mean_scalar_accuracy": quality,
            "mean_strict_scalar_accuracy": quality,
            "mean_macro_list_f1": quality,
            "mean_macro_label_list_f1": quality,
            "mean_summary_exact_f1": quality,
        },
        "provider_telemetry": {
            "total_duration_ms": 1000,
            "mean_success_latency_ms": 100,
            "p95_success_latency_ms": 120,
            "estimated_cost_usd": cost,
            "escalation_rate": 0.1,
            "error_rate": 0.0,
            "models_used": ["model-a"],
            "route_tiers": ["economy", "standard"],
            "cost_coverage": 1.0,
        },
    }


def test_comparator_reports_quality_and_cost_deltas():
    comparison = compare_reports(
        _report(quality=0.95, cost=0.01),
        _report(quality=0.94, cost=0.02),
    )
    assert comparison["quality"]["mean_scalar_accuracy"]["delta"] == pytest.approx(0.01)
    assert comparison["runtime"]["estimated_cost_usd"]["delta"] == pytest.approx(-0.01)
    assert "hiring outcomes" in comparison["claim_boundary"]


def test_comparator_rejects_different_dataset_versions():
    with pytest.raises(ValueError, match="dataset_sha256 differs"):
        compare_reports(
            _report(quality=0.95, cost=0.01, dataset_sha="adaptive"),
            _report(quality=0.95, cost=0.01, dataset_sha="single"),
        )
