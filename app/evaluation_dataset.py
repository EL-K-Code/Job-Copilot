from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import re
from typing import Any

from pydantic import ValidationError

from app.evaluation import LIST_FIELDS, SCALAR_FIELDS
from app.schemas import JobAnalysis


CASE_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
EXPECTED_FIELDS = frozenset(JobAnalysis.model_fields)
ALLOWED_DIFFICULTIES = {"easy", "medium", "hard"}


class BenchmarkValidationError(ValueError):
    """Raised when a benchmark file or case violates the annotation contract."""


def _require_nonempty_string(value: Any, field_name: str, case_id: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BenchmarkValidationError(
            f"Case '{case_id}' requires a non-empty string for '{field_name}'."
        )
    return value.strip()


def validate_benchmark_case(raw_case: Any, line_number: int | None = None) -> dict[str, Any]:
    """Validate one benchmark case and return a normalized dictionary."""
    location = f" on line {line_number}" if line_number is not None else ""
    if not isinstance(raw_case, dict):
        raise BenchmarkValidationError(f"Benchmark case{location} must be a JSON object.")

    case_id = _require_nonempty_string(raw_case.get("id"), "id", f"line-{line_number}")
    if not CASE_ID_PATTERN.fullmatch(case_id):
        raise BenchmarkValidationError(
            f"Case '{case_id}' must use a lowercase kebab-case identifier."
        )

    job_text = _require_nonempty_string(raw_case.get("job_text"), "job_text", case_id)
    if len(job_text) < 80:
        raise BenchmarkValidationError(
            f"Case '{case_id}' job_text is too short to represent a useful offer."
        )

    expected = raw_case.get("expected")
    if not isinstance(expected, dict):
        raise BenchmarkValidationError(
            f"Case '{case_id}' requires an 'expected' JSON object."
        )

    expected_keys = set(expected)
    missing_fields = sorted(EXPECTED_FIELDS - expected_keys)
    unknown_fields = sorted(expected_keys - EXPECTED_FIELDS)
    if missing_fields:
        raise BenchmarkValidationError(
            f"Case '{case_id}' is missing expected fields: {', '.join(missing_fields)}."
        )
    if unknown_fields:
        raise BenchmarkValidationError(
            f"Case '{case_id}' has unknown expected fields: {', '.join(unknown_fields)}."
        )

    try:
        validated_expected = JobAnalysis(**expected).model_dump()
    except ValidationError as exc:
        raise BenchmarkValidationError(
            f"Case '{case_id}' has an invalid expected annotation: {exc}"
        ) from exc

    for field in SCALAR_FIELDS:
        _require_nonempty_string(validated_expected[field], f"expected.{field}", case_id)

    for field in LIST_FIELDS:
        values = validated_expected[field]
        if not isinstance(values, list):
            raise BenchmarkValidationError(
                f"Case '{case_id}' expected.{field} must be a list."
            )
        normalized = [str(value).strip() for value in values if str(value).strip()]
        if len(normalized) != len(set(item.casefold() for item in normalized)):
            raise BenchmarkValidationError(
                f"Case '{case_id}' expected.{field} contains duplicate annotations."
            )
        validated_expected[field] = normalized

    metadata = raw_case.get("metadata", {})
    if not isinstance(metadata, dict):
        raise BenchmarkValidationError(
            f"Case '{case_id}' metadata must be a JSON object when provided."
        )

    normalized_metadata: dict[str, str] = {}
    for field in ("source_type", "language", "track", "difficulty"):
        normalized_metadata[field] = _require_nonempty_string(
            metadata.get(field), f"metadata.{field}", case_id
        )

    if normalized_metadata["difficulty"] not in ALLOWED_DIFFICULTIES:
        allowed = ", ".join(sorted(ALLOWED_DIFFICULTIES))
        raise BenchmarkValidationError(
            f"Case '{case_id}' metadata.difficulty must be one of: {allowed}."
        )

    return {
        "id": case_id,
        "metadata": normalized_metadata,
        "job_text": job_text,
        "expected": validated_expected,
    }


def load_benchmark_cases(path: Path) -> list[dict[str, Any]]:
    """Load and validate a JSONL benchmark, including unique case identifiers."""
    if not path.exists():
        raise FileNotFoundError(f"Benchmark file not found: {path}")

    cases: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    with path.open("r", encoding="utf-8") as file_handle:
        for line_number, line in enumerate(file_handle, start=1):
            normalized_line = line.strip()
            if not normalized_line:
                continue
            try:
                raw_case = json.loads(normalized_line)
            except json.JSONDecodeError as exc:
                raise BenchmarkValidationError(
                    f"Invalid JSON on line {line_number} of {path}: {exc.msg}."
                ) from exc

            case = validate_benchmark_case(raw_case, line_number=line_number)
            if case["id"] in seen_ids:
                raise BenchmarkValidationError(
                    f"Duplicate benchmark id '{case['id']}' on line {line_number}."
                )
            seen_ids.add(case["id"])
            cases.append(case)

    if not cases:
        raise BenchmarkValidationError(f"Benchmark file is empty: {path}")

    return cases


def summarize_benchmark(cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Return a compact coverage summary for a validated benchmark."""
    tracks = Counter(case["metadata"]["track"] for case in cases)
    difficulties = Counter(case["metadata"]["difficulty"] for case in cases)
    languages = Counter(case["metadata"]["language"] for case in cases)
    source_types = Counter(case["metadata"]["source_type"] for case in cases)

    return {
        "number_of_cases": len(cases),
        "unique_tracks": len(tracks),
        "tracks": dict(sorted(tracks.items())),
        "difficulties": dict(sorted(difficulties.items())),
        "languages": dict(sorted(languages.items())),
        "source_types": dict(sorted(source_types.items())),
    }
