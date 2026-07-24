from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.evaluation_dataset import (
    BenchmarkValidationError,
    load_benchmark_cases,
    summarize_benchmark,
    validate_benchmark_case,
)


def _valid_case(case_id: str = "sample-role") -> dict:
    return {
        "id": case_id,
        "metadata": {
            "source_type": "synthetic",
            "language": "en",
            "track": "agentic_ai",
            "difficulty": "medium",
        },
        "job_text": (
            "Sample Labs is hiring an AI Engineer in Paris. The role includes "
            "building reliable evaluation pipelines, testing models and documenting "
            "results. Python is required and Docker is preferred."
        ),
        "expected": {
            "company": "Sample Labs",
            "role": "AI Engineer",
            "location": "Paris",
            "contract_type": "full-time",
            "start_date": "Unknown",
            "missions_summary": ["build evaluation pipelines", "test models"],
            "required_skills": ["Python"],
            "preferred_skills": ["Docker"],
            "tools_and_stack": ["Python", "Docker"],
            "profile_summary": "A rigorous AI engineer.",
            "domain_focus": ["AI evaluation"],
            "key_highlights_for_candidate": ["Python", "evaluation experience"],
        },
    }


def test_validate_benchmark_case_accepts_complete_annotation() -> None:
    validated = validate_benchmark_case(_valid_case())

    assert validated["id"] == "sample-role"
    assert validated["expected"]["company"] == "Sample Labs"
    assert validated["metadata"]["difficulty"] == "medium"


def test_validate_benchmark_case_rejects_missing_expected_field() -> None:
    case = _valid_case()
    del case["expected"]["domain_focus"]

    with pytest.raises(BenchmarkValidationError, match="missing expected fields"):
        validate_benchmark_case(case)


def test_validate_benchmark_case_rejects_duplicate_annotations() -> None:
    case = _valid_case()
    case["expected"]["required_skills"] = ["Python", "python"]

    with pytest.raises(BenchmarkValidationError, match="duplicate annotations"):
        validate_benchmark_case(case)


def test_load_benchmark_cases_rejects_duplicate_ids(tmp_path: Path) -> None:
    dataset = tmp_path / "benchmark.jsonl"
    case = _valid_case()
    dataset.write_text(
        json.dumps(case) + "\n" + json.dumps(case) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(BenchmarkValidationError, match="Duplicate benchmark id"):
        load_benchmark_cases(dataset)


def test_load_benchmark_cases_rejects_invalid_json(tmp_path: Path) -> None:
    dataset = tmp_path / "benchmark.jsonl"
    dataset.write_text("{not-json}\n", encoding="utf-8")

    with pytest.raises(BenchmarkValidationError, match="Invalid JSON"):
        load_benchmark_cases(dataset)


def test_summarize_benchmark_reports_coverage() -> None:
    first = validate_benchmark_case(_valid_case("first-role"))
    second_raw = _valid_case("second-role")
    second_raw["metadata"]["track"] = "mlops"
    second_raw["metadata"]["difficulty"] = "hard"
    second = validate_benchmark_case(second_raw)

    summary = summarize_benchmark([first, second])

    assert summary["number_of_cases"] == 2
    assert summary["unique_tracks"] == 2
    assert summary["difficulties"] == {"hard": 1, "medium": 1}
