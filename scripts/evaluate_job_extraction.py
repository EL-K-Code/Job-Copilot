from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from statistics import mean

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

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


def run_evaluation(cases: list[dict]) -> dict:
    case_results: list[dict] = []

    for case in cases:
        prediction = analyze_job_offer(case["job_text"])
        metrics = evaluate_job_analysis(prediction, case["expected"])
        case_results.append(
            {
                "id": case["id"],
                "prediction": prediction.model_dump(),
                "expected": case["expected"],
                "metrics": metrics,
            }
        )

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
        "cases": case_results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate structured job-offer extraction on JSONL cases."
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("evaluation/job_offers.sample.jsonl"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evaluation/results/job_extraction_report.json"),
    )
    args = parser.parse_args()

    report = run_evaluation(load_cases(args.dataset))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "number_of_cases": report["number_of_cases"],
                "mean_scalar_accuracy": report["mean_scalar_accuracy"],
                "mean_macro_list_f1": report["mean_macro_list_f1"],
                "output": str(args.output),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
