from __future__ import annotations

import argparse
import json
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
        "schema_version": 1,
        "benchmark_type": "synthetic_engineering_regression",
        "dataset": "evaluation/retrieval_cases.v1.jsonl",
        "number_of_cases": int(report.get("number_of_cases", 0)),
        "k": int(report.get("k", 5)),
        "latency_scope": str(report.get("latency_scope", "unknown")),
        "strategies": aggregates,
        "best_by_metric": best_by_metric,
        "ties_by_metric": ties_by_metric,
        "delta_vs_dense": delta_vs_dense,
        "interpretation": (
            "Ranking quality and warm-process retrieval latency on labeled synthetic "
            "profile-memory queries; not recruiter outcomes."
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
