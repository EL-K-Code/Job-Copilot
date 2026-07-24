from __future__ import annotations

import math
import re
import unicodedata
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

SCORED_LIST_FIELDS = (
    "missions_summary",
    "required_skills",
    "preferred_skills",
    "tools_and_stack",
    "domain_focus",
)

UNSCORED_LIST_FIELDS = ("key_highlights_for_candidate",)
LIST_FIELDS = SCORED_LIST_FIELDS
GROUNDING_LABELS = ("supported", "unsupported", "ambiguous")

EVALUATION_ALIASES = {
    "natural language processing": "nlp",
    "retrieval augmented generation": "rag",
    "large language models": "llm",
    "large language model": "llm",
    "llms": "llm",
    "application programming interfaces": "api",
    "application programming interface": "api",
    "apis": "api",
    "machine learning": "ml",
    "deep learning": "dl",
    "computer vision": "cv",
    "artificial intelligence": "ai",
    "sentence berts": "sbert",
    "sentence bert": "sbert",
    "continuous integration continuous deployment": "cicd",
    "ci cd": "cicd",
}


def normalize_text(value: str) -> str:
    return " ".join(value.strip().casefold().split())


def normalize_evaluation_item(value: str) -> str:
    """Normalize punctuation and replace documented expansions with acronyms."""
    text = unicodedata.normalize("NFKC", str(value)).casefold()
    text = text.replace("&", " and ")
    text = re.sub(r"[-/()]", " ", text)
    text = re.sub(r"[^\w+#.]+", " ", text)
    text = " ".join(text.split())

    for alias in sorted(EVALUATION_ALIASES, key=len, reverse=True):
        canonical = EVALUATION_ALIASES[alias]
        text = re.sub(rf"(?<!\w){re.escape(alias)}(?!\w)", canonical, text)

    # Expanded and abbreviated forms often appear together, for example
    # "natural language processing (NLP)" -> "nlp nlp". Remove duplicate
    # tokens while preserving the rest of the phrase, such as "llm evaluation".
    tokens: list[str] = []
    for token in text.split():
        if not tokens or token != tokens[-1]:
            tokens.append(token)
    return " ".join(tokens)


def normalize_items(values: Iterable[str]) -> set[str]:
    return {
        normalized
        for value in values
        if (normalized := normalize_evaluation_item(str(value)))
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
    for field in SCORED_LIST_FIELDS:
        if field not in expected:
            continue
        list_scores[field] = set_precision_recall_f1(
            list(predicted_data.get(field, [])),
            list(expected[field]),
        )

    unscored_fields = {
        field: {
            "prediction": list(predicted_data.get(field, [])),
            "expected_reference": list(expected.get(field, [])),
            "reason": "Generated recommendation field; excluded from extraction F1.",
        }
        for field in UNSCORED_LIST_FIELDS
        if field in predicted_data or field in expected
    }

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
        "scored_list_fields": list(SCORED_LIST_FIELDS),
        "scalar_fields": scalar_scores,
        "list_fields": list_scores,
        "unscored_fields": unscored_fields,
    }


def recall_at_k(
    ranked_ids: Iterable[str],
    relevant_ids: Iterable[str],
    k: int,
) -> float:
    if k < 1:
        raise ValueError("k must be greater than or equal to 1.")
    relevant = set(relevant_ids)
    if not relevant:
        return 1.0
    retrieved = set(list(ranked_ids)[:k])
    return len(retrieved & relevant) / len(relevant)


def reciprocal_rank(
    ranked_ids: Iterable[str],
    relevant_ids: Iterable[str],
) -> float:
    relevant = set(relevant_ids)
    if not relevant:
        return 1.0
    for rank, item_id in enumerate(ranked_ids, start=1):
        if item_id in relevant:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(
    ranked_ids: Iterable[str],
    relevant_ids: Iterable[str],
    k: int,
) -> float:
    if k < 1:
        raise ValueError("k must be greater than or equal to 1.")
    relevant = set(relevant_ids)
    if not relevant:
        return 1.0

    ranked = list(ranked_ids)[:k]
    dcg = sum(
        1.0 / math.log2(rank + 1)
        for rank, item_id in enumerate(ranked, start=1)
        if item_id in relevant
    )
    ideal_hits = min(len(relevant), k)
    idcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))
    return dcg / idcg if idcg else 0.0


def evaluate_retrieval_ranking(
    ranked_ids: list[str],
    relevant_ids: list[str],
    k_values: tuple[int, ...] = (1, 3, 5),
) -> dict[str, float]:
    metrics: dict[str, float] = {
        "mrr": reciprocal_rank(ranked_ids, relevant_ids),
    }
    for k in k_values:
        metrics[f"recall@{k}"] = recall_at_k(ranked_ids, relevant_ids, k)
        metrics[f"ndcg@{k}"] = ndcg_at_k(ranked_ids, relevant_ids, k)
    return metrics


def evaluate_grounding_labels(
    predicted_labels: list[str],
    expected_labels: list[str],
) -> dict[str, Any]:
    if len(predicted_labels) != len(expected_labels):
        raise ValueError("Predicted and expected label lists must have the same length.")

    invalid = {
        label
        for label in [*predicted_labels, *expected_labels]
        if label not in GROUNDING_LABELS
    }
    if invalid:
        raise ValueError(f"Unsupported grounding labels: {sorted(invalid)}")

    total = len(expected_labels)
    accuracy = (
        sum(pred == gold for pred, gold in zip(predicted_labels, expected_labels)) / total
        if total
        else 0.0
    )

    per_label: dict[str, dict[str, float]] = {}
    for label in GROUNDING_LABELS:
        true_positive = sum(
            pred == label and gold == label
            for pred, gold in zip(predicted_labels, expected_labels)
        )
        false_positive = sum(
            pred == label and gold != label
            for pred, gold in zip(predicted_labels, expected_labels)
        )
        false_negative = sum(
            pred != label and gold == label
            for pred, gold in zip(predicted_labels, expected_labels)
        )
        precision = (
            true_positive / (true_positive + false_positive)
            if true_positive + false_positive
            else 0.0
        )
        recall = (
            true_positive / (true_positive + false_negative)
            if true_positive + false_negative
            else 0.0
        )
        f1 = (
            2 * precision * recall / (precision + recall)
            if precision + recall
            else 0.0
        )
        per_label[label] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
        }

    macro_f1 = sum(item["f1"] for item in per_label.values()) / len(per_label)
    expected_counts = Counter(expected_labels)

    return {
        "accuracy": accuracy,
        "macro_f1": macro_f1,
        "per_label": per_label,
        "expected_distribution": dict(expected_counts),
    }
