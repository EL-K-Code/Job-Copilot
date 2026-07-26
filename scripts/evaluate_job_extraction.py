from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.evaluation import (
    SCALAR_FIELDS,
    SCORED_LIST_FIELDS,
    SUMMARY_LIST_FIELDS,
    evaluate_job_analysis,
)
from app.services.llm import analyze_job_offer
from app.services.llm_telemetry import (
    capture_llm_telemetry,
    serialize_llm_events,
    summarize_llm_events,
)
from app.services.model_provider import configured_model_label


EVALUATION_PROTOCOL_VERSION = "1.3.0"


def load_cases(path: Path) -> list[dict]:
    cases: list[dict] = []
    with path.open("r", encoding="utf-8") as file_handle:
        for line_number, line in enumerate(file_handle, start=1):
            normalized = line.strip()
            if not normalized:
                continue
            try:
                cases.append(json.loads(normalized))
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid JSON on line {line_number} of {path}."
                ) from exc
    return cases


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _mean_metric(case_results: list[dict], metric_name: str) -> float:
    return (
        mean(item["metrics"][metric_name] for item in case_results)
        if case_results
        else 0.0
    )


def summarize_results(case_results: list[dict]) -> dict:
    scalar_by_field = {
        field: mean(
            item["metrics"]["scalar_fields"][field]
            for item in case_results
            if field in item["metrics"]["scalar_fields"]
        )
        for field in SCALAR_FIELDS
        if any(field in item["metrics"]["scalar_fields"] for item in case_results)
    }
    strict_scalar_by_field = {
        field: mean(
            item["metrics"]["strict_scalar_fields"][field]
            for item in case_results
            if field in item["metrics"]["strict_scalar_fields"]
        )
        for field in SCALAR_FIELDS
        if any(
            field in item["metrics"]["strict_scalar_fields"]
            for item in case_results
        )
    }
    list_f1_by_field = {
        field: mean(
            item["metrics"]["list_fields"][field]["f1"]
            for item in case_results
            if field in item["metrics"]["list_fields"]
        )
        for field in SCORED_LIST_FIELDS
        if any(field in item["metrics"]["list_fields"] for item in case_results)
    }
    summary_exact_f1_by_field = {
        field: mean(
            item["metrics"]["summary_fields"][field]["f1"]
            for item in case_results
            if field in item["metrics"]["summary_fields"]
        )
        for field in SUMMARY_LIST_FIELDS
        if any(field in item["metrics"]["summary_fields"] for item in case_results)
    }

    return {
        "number_of_cases": len(case_results),
        "mean_scalar_accuracy": _mean_metric(case_results, "scalar_accuracy"),
        "mean_strict_scalar_accuracy": _mean_metric(
            case_results, "strict_scalar_accuracy"
        ),
        "mean_macro_list_f1": _mean_metric(case_results, "macro_list_f1"),
        "mean_macro_label_list_f1": _mean_metric(
            case_results, "macro_label_list_f1"
        ),
        "mean_summary_exact_f1": _mean_metric(case_results, "summary_exact_f1"),
        "scalar_accuracy_by_field": scalar_by_field,
        "strict_scalar_accuracy_by_field": strict_scalar_by_field,
        "list_f1_by_field": list_f1_by_field,
        "summary_exact_f1_by_field": summary_exact_f1_by_field,
    }


def grouped_summaries(case_results: list[dict], field: str) -> dict[str, dict]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for item in case_results:
        groups[str(item.get(field, "unknown"))].append(item)
    return {
        group_name: summarize_results(group_items)
        for group_name, group_items in sorted(groups.items())
    }


def summarize_provider_telemetry(case_results: list[dict]) -> dict:
    events = [
        event
        for item in case_results
        for event in item.get("llm_telemetry", [])
    ]
    final_providers = Counter(
        item.get("llm_telemetry_summary", {}).get("final_provider")
        for item in case_results
        if item.get("llm_telemetry_summary", {}).get("final_provider")
    )
    return {
        **summarize_llm_events(events),
        "successful_cases_by_provider": dict(final_providers),
        "cases_using_fallback": sum(
            bool(item.get("llm_telemetry_summary", {}).get("fallback_used"))
            for item in case_results
        ),
        "privacy_boundary": (
            "Provider, model, operation, latency, status and available token counts only; "
            "prompts, outputs, API keys and raw provider errors are not recorded."
        ),
    }


def run_evaluation(cases: list[dict]) -> dict:
    case_results: list[dict] = []

    for case in cases:
        with capture_llm_telemetry() as telemetry_events:
            prediction = analyze_job_offer(case["job_text"])
        metrics = evaluate_job_analysis(prediction, case["expected"])
        serialized_events = serialize_llm_events(telemetry_events)
        case_results.append(
            {
                "id": case["id"],
                "language": case.get("language", "unknown"),
                "category": case.get("category", "unknown"),
                "difficulty": case.get("difficulty", "unknown"),
                "prediction": prediction.model_dump(),
                "expected": case["expected"],
                "metrics": metrics,
                "llm_telemetry": serialized_events,
                "llm_telemetry_summary": summarize_llm_events(serialized_events),
            }
        )

    return {
        "aggregate": summarize_results(case_results),
        "provider_telemetry": summarize_provider_telemetry(case_results),
        "by_language": grouped_summaries(case_results, "language"),
        "by_category": grouped_summaries(case_results, "category"),
        "by_difficulty": grouped_summaries(case_results, "difficulty"),
        "cases": case_results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate structured job-offer extraction on JSONL cases."
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("evaluation/job_offers.v1.jsonl"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evaluation/results/job_extraction_report.json"),
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Evaluate only the first N cases. Zero means the full dataset.",
    )
    parser.add_argument(
        "--benchmark-version",
        default="1.0.0",
        help="Version label for the selected dataset.",
    )
    args = parser.parse_args()

    if args.limit < 0:
        raise ValueError("--limit cannot be negative.")

    cases = load_cases(args.dataset)
    if args.limit:
        cases = cases[: args.limit]

    evaluation = run_evaluation(cases)
    report = {
        "task": "structured_job_offer_extraction",
        "benchmark_version": args.benchmark_version,
        "evaluation_protocol_version": EVALUATION_PROTOCOL_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": configured_model_label(),
        "dataset": str(args.dataset),
        "dataset_sha256": sha256_file(args.dataset),
        "prompt_sha256": sha256_file(PROJECT_ROOT / "app" / "prompts.py"),
        "metric_definition": {
            "scored_scalar_fields": list(SCALAR_FIELDS),
            "contract_type_scoring": {
                "primary": "broad multilingual normalized category match",
                "diagnostic": "strict normalized text match",
            },
            "scored_closed_label_list_fields": list(SCORED_LIST_FIELDS),
            "summary_diagnostic_fields": list(SUMMARY_LIST_FIELDS),
            "summary_diagnostic": (
                "Exact normalized lexical F1, reported separately because valid paraphrases may differ."
            ),
            "unscored_generated_fields": ["key_highlights_for_candidate"],
            "acronym_normalization": True,
        },
        **evaluation,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "benchmark_version": report["benchmark_version"],
                "evaluation_protocol_version": report["evaluation_protocol_version"],
                "model": report["model"],
                "provider_telemetry": report["provider_telemetry"],
                **report["aggregate"],
                "output": str(args.output),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
