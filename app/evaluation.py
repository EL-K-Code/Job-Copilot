from __future__ import annotations

import math
from collections import Counter
from typing import Any, Iterable

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

GROUNDING_LABELS = ("supported", "unsupported", "ambiguous")


def normalize_text(value: str) -> str:
    return " ".join(value.strip().casefold().split())


def normalize_items(values: Iterable[str]) -> set[str]:
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


def recall_at_k(
    retrieved_ids: list[str],
    relevant_ids: list[str],
    k: int,
) -> float:
    """Return the fraction of relevant memories retrieved in the first k results."""
    if k < 1:
        raise ValueError("k must be greater than or equal to 1.")

    relevant = normalize_items(relevant_ids)
    if not relevant:
        return 1.0

    retrieved = normalize_items(retrieved_ids[:k])
    return len(retrieved & relevant) / len(relevant)


def reciprocal_rank(
    retrieved_ids: list[str],
    relevant_ids: list[str],
) -> float:
    """Return the reciprocal rank of the first relevant result."""
    relevant = normalize_items(relevant_ids)
    for rank, item_id in enumerate(retrieved_ids, start=1):
        if normalize_text(item_id) in relevant:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(
    retrieved_ids: list[str],
    relevance_by_id: dict[str, int | float],
    k: int,
) -> float:
    """Compute normalized discounted cumulative gain with graded relevance."""
    if k < 1:
        raise ValueError("k must be greater than or equal to 1.")

    normalized_relevance = {
        normalize_text(item_id): max(float(score), 0.0)
        for item_id, score in relevance_by_id.items()
    }

    def dcg(scores: list[float]) -> float:
        return sum(
            (2**score - 1) / math.log2(rank + 1)
            for rank, score in enumerate(scores, start=1)
        )

    observed_scores = [
        normalized_relevance.get(normalize_text(item_id), 0.0)
        for item_id in retrieved_ids[:k]
    ]
    ideal_scores = sorted(normalized_relevance.values(), reverse=True)[:k]
    ideal_dcg = dcg(ideal_scores)
    return dcg(observed_scores) / ideal_dcg if ideal_dcg else 1.0


def evaluate_retrieval_ranking(
    retrieved_ids: list[str],
    relevant_ids: list[str],
    relevance_by_id: dict[str, int | float] | None = None,
    ks: tuple[int, ...] = (1, 3, 5),
) -> dict[str, float]:
    """Evaluate one retrieval ranking with Recall@k, MRR and NDCG@k."""
    if any(k < 1 for k in ks):
        raise ValueError("All k values must be greater than or equal to 1.")

    graded = relevance_by_id or {item_id: 1 for item_id in relevant_ids}
    metrics: dict[str, float] = {
        "reciprocal_rank": reciprocal_rank(retrieved_ids, relevant_ids),
    }
    for k in ks:
        metrics[f"recall_at_{k}"] = recall_at_k(retrieved_ids, relevant_ids, k)
        metrics[f"ndcg_at_{k}"] = ndcg_at_k(retrieved_ids, graded, k)
    return metrics


def summarize_grounding_annotations(
    annotations: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Aggregate human claim-level grounding labels.

    Each annotation must contain a ``label`` equal to supported, unsupported,
    or ambiguous. Empty annotation sets return zero rates rather than a
    misleading perfect score.
    """
    counts = Counter()
    for annotation in annotations:
        label = normalize_text(str(annotation.get("label", "")))
        if label not in GROUNDING_LABELS:
            raise ValueError(
                f"Invalid grounding label: {annotation.get('label')!r}. "
                f"Expected one of {GROUNDING_LABELS}."
            )
        counts[label] += 1

    total = sum(counts.values())
    rates = {
        f"{label}_rate": counts[label] / total if total else 0.0
        for label in GROUNDING_LABELS
    }

    return {
        "number_of_claims": total,
        "counts": {label: counts[label] for label in GROUNDING_LABELS},
        **rates,
        "unsupported_claim_rate": rates["unsupported_rate"],
    }
