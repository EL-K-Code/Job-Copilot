from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


QUALITY_METRICS = (
    "mean_scalar_accuracy",
    "mean_strict_scalar_accuracy",
    "mean_macro_list_f1",
    "mean_macro_label_list_f1",
    "mean_summary_exact_f1",
)


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def _number(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None


def compare_reports(adaptive: dict[str, Any], single: dict[str, Any]) -> dict[str, Any]:
    for field in ("dataset_sha256", "prompt_sha256", "evaluation_protocol_version"):
        if adaptive.get(field) != single.get(field):
            raise ValueError(
                f"Reports are not comparable: {field} differs ({adaptive.get(field)!r} vs {single.get(field)!r})."
            )

    adaptive_quality = dict(adaptive.get("aggregate", {}) or {})
    single_quality = dict(single.get("aggregate", {}) or {})
    adaptive_runtime = dict(adaptive.get("provider_telemetry", {}) or {})
    single_runtime = dict(single.get("provider_telemetry", {}) or {})

    quality = {}
    for metric in QUALITY_METRICS:
        a = _number(adaptive_quality.get(metric))
        s = _number(single_quality.get(metric))
        quality[metric] = {
            "adaptive": a,
            "single": s,
            "delta": (a - s) if a is not None and s is not None else None,
        }

    runtime = {}
    for metric in (
        "total_duration_ms",
        "mean_success_latency_ms",
        "p95_success_latency_ms",
        "estimated_cost_usd",
        "escalation_rate",
        "error_rate",
    ):
        a = _number(adaptive_runtime.get(metric))
        s = _number(single_runtime.get(metric))
        runtime[metric] = {
            "adaptive": a,
            "single": s,
            "delta": (a - s) if a is not None and s is not None else None,
        }

    return {
        "task": adaptive.get("task"),
        "benchmark_version": adaptive.get("benchmark_version"),
        "evaluation_protocol_version": adaptive.get("evaluation_protocol_version"),
        "dataset_sha256": adaptive.get("dataset_sha256"),
        "prompt_sha256": adaptive.get("prompt_sha256"),
        "quality": quality,
        "runtime": runtime,
        "adaptive_models_used": adaptive_runtime.get("models_used", []),
        "single_models_used": single_runtime.get("models_used", []),
        "adaptive_route_tiers": adaptive_runtime.get("route_tiers", []),
        "single_route_tiers": single_runtime.get("route_tiers", []),
        "adaptive_cost_coverage": adaptive_runtime.get("cost_coverage"),
        "single_cost_coverage": single_runtime.get("cost_coverage"),
        "claim_boundary": (
            "This comparison is valid only for the versioned synthetic extraction benchmark. "
            "It is not evidence of recruiter or hiring outcomes."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare adaptive and single-model JobCopilot extraction reports."
    )
    parser.add_argument("--adaptive", type=Path, required=True)
    parser.add_argument("--single", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evaluation/results/model_routing_comparison.json"),
    )
    args = parser.parse_args()

    comparison = compare_reports(_load(args.adaptive), _load(args.single))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(comparison, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps(comparison, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
