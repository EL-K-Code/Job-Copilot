from __future__ import annotations

from typing import Any

from app.schemas import JobAnalysis


SCALAR_FIELDS = (
    "company",
    "role",
    "location",
    "contract_type",
    "start_date",
)

LIST_FIELDS = (
    "missions_summary",
    "required_skills",
    "preferred_skills",
    "tools_and_stack",
    "domain_focus",
    "key_highlights_for_candidate",
)


def normalize_text(value: str) -> str:
    return " ".join(value.strip().casefold().split())


def normalize_items(values: list[str]) -> set[str]:
    return {
        normalized
        for value in values
        if (normalized := normalize_text(str(value)))
    }


def set_precision_recall_f1(
    predicted: list[str],
    expected: list[str],
) -> dict[str, float]:
    predicted_set = normalize_items(predicted)
    expected_set = normalize_items(expected)
    true_positives = len(predicted_set & expected_set)

    precision = (
        true_positives / len(predicted_set)
        if predicted_set
        else float(not expected_set)
    )
    recall = (
        true_positives / len(expected_set)
        if expected_set
        else float(not predicted_set)
    )
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0
    )

    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def evaluate_job_analysis(
    predicted: JobAnalysis | dict[str, Any],
    expected: dict[str, Any],
) -> dict[str, Any]:
    predicted_data = (
        predicted.model_dump()
        if isinstance(predicted, JobAnalysis)
        else predicted
    )

    scalar_scores: dict[str, float] = {}
    for field in SCALAR_FIELDS:
        if field not in expected:
            continue
        scalar_scores[field] = float(
            normalize_text(str(predicted_data.get(field, "")))
            == normalize_text(str(expected[field]))
        )

    list_scores: dict[str, dict[str, float]] = {}
    for field in LIST_FIELDS:
        if field not in expected:
            continue
        list_scores[field] = set_precision_recall_f1(
            list(predicted_data.get(field, [])),
            list(expected[field]),
        )

    scalar_accuracy = (
        sum(scalar_scores.values()) / len(scalar_scores)
        if scalar_scores
        else 0.0
    )
    macro_list_f1 = (
        sum(metrics["f1"] for metrics in list_scores.values()) / len(list_scores)
        if list_scores
        else 0.0
    )

    return {
        "scalar_accuracy": scalar_accuracy,
        "macro_list_f1": macro_list_f1,
        "scalar_fields": scalar_scores,
        "list_fields": list_scores,
    }
