from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import settings
from app.evaluation import evaluate_job_analysis
from app.services.llm import analyze_job_offer


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


def summarize_results(case_results: list[dict]) -> dict:
    return {
        "number_of_cases": len(case_results),
        "mean_scalar_accuracy": (
            mean(item["metrics"]["scalar_accuracy"] for item in case_results)
            if case_results
            else 0.0
        ),
        "mean_macro_list_f1": (
            mean(item["metrics"]["macro_list_f1"] for item in case_results)
            if case_results
            else 0.0
        ),
    }


def grouped_summaries(case_results: list[dict], field: str) -> dict[str, dict]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for item in case_results:
        groups[str(item.get(field, "unknown"))].append(item)
    return {
        group_name: summarize_results(group_items)
        for group_name, group_items in sorted(groups.items())
    }


def run_evaluation(cases: list[dict]) -> dict:
    case_results: list[dict] = []

    for case in cases:
        prediction = analyze_job_offer(case["job_text"])
        metrics = evaluate_job_analysis(prediction, case["expected"])
        case_results.append(
            {
                "id": case["id"],
                "language": case.get("language", "unknown"),
                "category": case.get("category", "unknown"),
                "difficulty": case.get("difficulty", "unknown"),
                "prediction": prediction.model_dump(),
                "expected": case["expected"],
                "metrics": metrics,
            }
        )

    return {
        "aggregate": summarize_results(case_results),
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
        "--manifest",
        type=Path,
        default=Path("evaluation/benchmark_manifest.v1.json"),
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
    args = parser.parse_args()

    if args.limit < 0:
        raise ValueError("--limit cannot be negative.")

    cases = load_cases(args.dataset)
    if args.limit:
        cases = cases[: args.limit]

    evaluation = run_evaluation(cases)
    manifest = (
        json.loads(args.manifest.read_text(encoding="utf-8"))
        if args.manifest.exists()
        else {}
    )
    report = {
        "task": "structured_job_offer_extraction",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "benchmark_version": manifest.get("version", "unknown"),
        "model": settings.anthropic_model,
        "dataset": str(args.dataset),
        "dataset_sha256": sha256_file(args.dataset),
        "prompt_sha256": sha256_file(PROJECT_ROOT / "app" / "prompts.py"),
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
                "model": report["model"],
                **report["aggregate"],
                "output": str(args.output),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
