from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any


QUALITY_METRICS = (
    "mrr",
    "recall@1",
    "recall@3",
    "recall@5",
    "ndcg@1",
    "ndcg@3",
    "ndcg@5",
)
LATENCY_METRICS = (
    "mean_latency_ms",
    "p50_latency_ms",
    "p95_latency_ms",
)
PUBLISHED_METRICS = (*QUALITY_METRICS, *LATENCY_METRICS)
_BOOTSTRAP_SAMPLES = 2000
_BOOTSTRAP_SEED = 20260909
_TIE_EPSILON = 1e-12


def _percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = round(quantile * (len(ordered) - 1))
    return float(ordered[max(0, min(len(ordered) - 1, index))])


def _case_metrics_by_id(payload: Any) -> dict[str, dict[str, float]]:
    if not isinstance(payload, dict):
        return {}
    output: dict[str, dict[str, float]] = {}
    for case in payload.get("cases", []) or []:
        if not isinstance(case, dict):
            continue
        case_id = str(case.get("id", "")).strip()
        metrics = case.get("metrics", {})
        if not case_id or not isinstance(metrics, dict):
            continue
        output[case_id] = {
            metric: float(metrics.get(metric, 0.0))
            for metric in QUALITY_METRICS
        }
    return output


def _paired_metric_summary(
    dense_values: list[float],
    challenger_values: list[float],
    *,
    samples: int = _BOOTSTRAP_SAMPLES,
    seed: int = _BOOTSTRAP_SEED,
) -> dict[str, Any]:
    if len(dense_values) != len(challenger_values):
        raise ValueError("Paired retrieval metric vectors must have the same length.")
    if not dense_values:
        return {}

    deltas = [
        challenger - dense
        for dense, challenger in zip(dense_values, challenger_values, strict=True)
    ]
    mean_delta = sum(deltas) / len(deltas)
    wins = sum(delta > _TIE_EPSILON for delta in deltas)
    losses = sum(delta < -_TIE_EPSILON for delta in deltas)
    ties = len(deltas) - wins - losses

    if len(deltas) == 1:
        ci_low = ci_high = mean_delta
    else:
        rng = random.Random(seed)
        bootstrap_means: list[float] = []
        for _ in range(samples):
            sampled = [deltas[rng.randrange(len(deltas))] for _ in deltas]
            bootstrap_means.append(sum(sampled) / len(sampled))
        ci_low = _percentile(bootstrap_means, 0.025)
        ci_high = _percentile(bootstrap_means, 0.975)

    return {
        "paired_cases": len(deltas),
        "mean_delta": mean_delta,
        "bootstrap_ci95": [ci_low, ci_high],
        "wins": wins,
        "ties": ties,
        "losses": losses,
        "bootstrap_samples": samples,
        "bootstrap_seed": seed,
    }


def _paired_quality_comparisons(strategies: dict[str, Any]) -> dict[str, Any]:
    dense_cases = _case_metrics_by_id(strategies.get("dense"))
    if not dense_cases:
        return {}

    comparisons: dict[str, Any] = {}
    for strategy, payload in strategies.items():
        strategy_name = str(strategy)
        if strategy_name == "dense":
            continue
        challenger_cases = _case_metrics_by_id(payload)
        common_ids = [case_id for case_id in dense_cases if case_id in challenger_cases]
        if not common_ids:
            continue

        comparisons[strategy_name] = {
            metric: _paired_metric_summary(
                [dense_cases[case_id][metric] for case_id in common_ids],
                [challenger_cases[case_id][metric] for case_id in common_ids],
                seed=_BOOTSTRAP_SEED + index,
            )
            for index, metric in enumerate(QUALITY_METRICS)
        }
    return comparisons


def build_summary(report: dict[str, Any]) -> dict[str, Any]:
    strategies = report.get("strategies", {})
    if not isinstance(strategies, dict) or not strategies:
        raise ValueError("Retrieval report must contain at least one strategy.")

    aggregates: dict[str, dict[str, float]] = {}
    for strategy, payload in strategies.items():
        aggregate = payload.get("aggregate", {}) if isinstance(payload, dict) else {}
        aggregates[str(strategy)] = {
            metric: float(aggregate.get(metric, 0.0))
            for metric in PUBLISHED_METRICS
        }

    best_by_metric: dict[str, str] = {}
    ties_by_metric: dict[str, list[str]] = {}
    strategy_order = list(aggregates)
    for metric in PUBLISHED_METRICS:
        values = [aggregates[name][metric] for name in strategy_order]
        best_value = min(values) if metric in LATENCY_METRICS else max(values)
        tied = [name for name in strategy_order if aggregates[name][metric] == best_value]
        best_by_metric[metric] = tied[0]
        if len(tied) > 1:
            ties_by_metric[metric] = tied

    dense = aggregates.get("dense")
    delta_vs_dense: dict[str, dict[str, float]] = {}
    if dense is not None:
        for strategy, metrics in aggregates.items():
            if strategy == "dense":
                continue
            delta_vs_dense[strategy] = {
                metric: metrics[metric] - dense[metric]
                for metric in PUBLISHED_METRICS
            }

    return {
        "schema_version": 2,
        "benchmark_type": "synthetic_engineering_regression",
        "dataset": "evaluation/retrieval_cases.v1.jsonl",
        "number_of_cases": int(report.get("number_of_cases", 0)),
        "k": int(report.get("k", 5)),
        "latency_scope": str(report.get("latency_scope", "unknown")),
        "strategies": aggregates,
        "best_by_metric": best_by_metric,
        "ties_by_metric": ties_by_metric,
        "delta_vs_dense": delta_vs_dense,
        "paired_vs_dense": _paired_quality_comparisons(strategies),
        "interpretation": (
            "Ranking quality and warm-process retrieval latency on labeled synthetic "
            "profile-memory queries; paired bootstrap intervals quantify uncertainty in "
            "quality deltas and are not recruiter-outcome confidence intervals."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create a compact, publishable retrieval benchmark summary."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("evaluation/results/retrieval_report.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evaluation/results/retrieval_summary.json"),
    )
    args = parser.parse_args()

    report = json.loads(args.input.read_text(encoding="utf-8"))
    summary = build_summary(report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
