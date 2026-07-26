from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from typing import Any

from app.schemas import JobAnalysis


_FIELD_WEIGHTS = {
    "required_skills": 5.0,
    "tools_and_stack": 4.0,
    "domain_focus": 4.0,
    "preferred_skills": 3.0,
    "role": 2.5,
    "missions_summary": 2.0,
}

_TYPE_PRIORITY = {
    "project": 0,
    "experience": 1,
    "skill": 2,
    "education": 3,
    "identity": 4,
    "preference": 5,
    "unknown": 6,
}

_ALIAS_PATTERNS = (
    (r"\bretrieval augmented generation\b", "rag"),
    (r"\bnatural language processing\b", "nlp"),
    (r"\blarge language models?\b", "llm"),
    (r"\bmachine learning\b", "ml"),
    (r"\bapplication programming interfaces?\b", "api"),
    (r"\bcontinuous integration(?: and| /|/) continuous deployment\b", "ci cd"),
)

# Atomic-memory topics can encode a narrow, auditable semantic relationship that
# lexical overlap alone cannot capture. These rules deliberately remain small and
# explicit instead of turning the relevance scorer into an opaque semantic model.
_TOPIC_SEMANTIC_TRIGGERS = {
    "human supervision": (
        "responsible ai",
        "trustworthy ai",
        "ai safety",
        "human oversight",
        "human in the loop",
    ),
    "evaluation metrics": (
        "model evaluation",
        "ai evaluation",
        "evaluation protocol",
        "evaluation protocols",
        "model failure mode",
        "model failure modes",
        "error analysis",
        "robustness testing",
        "calibration",
    ),
}

_SEMANTIC_TOPIC_DISCOUNT = 0.80

_STOPWORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "be",
    "build",
    "candidate",
    "for",
    "from",
    "in",
    "integrate",
    "is",
    "of",
    "on",
    "or",
    "the",
    "to",
    "using",
    "with",
}


def normalize_relevance_text(value: str) -> str:
    """Normalize technical text while preserving common AI acronyms."""
    text = unicodedata.normalize("NFKC", str(value)).casefold()
    text = text.replace("&", " and ")
    text = re.sub(r"[-_/]", " ", text)
    text = re.sub(r"[^\w+#.]+", " ", text)
    for pattern, replacement in _ALIAS_PATTERNS:
        text = re.sub(pattern, replacement, text)
    return " ".join(text.split())


def _term_tokens(value: str) -> set[str]:
    return {
        token
        for token in normalize_relevance_text(value).replace(".", " ").split()
        if len(token) > 1 and token not in _STOPWORDS
    }


def _ordered_unique(values: Iterable[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = " ".join(str(value).strip().split())
        key = normalize_relevance_text(normalized)
        if not normalized or not key or key in seen:
            continue
        seen.add(key)
        output.append(normalized)
    return output


def _contains_normalized_phrase(text: str, phrase: str) -> bool:
    normalized_text = f" {normalize_relevance_text(text)} "
    normalized_phrase = f" {normalize_relevance_text(phrase)} "
    return normalized_phrase in normalized_text


def _topic_semantically_aligns(memory_record: dict[str, Any], job_term: str) -> bool:
    """Return whether an atomic topic has an explicit controlled relation to a job term."""
    topic = normalize_relevance_text(str(memory_record.get("topic", "")))
    triggers = _TOPIC_SEMANTIC_TRIGGERS.get(topic, ())
    return any(_contains_normalized_phrase(job_term, trigger) for trigger in triggers)


def job_relevance_terms(job_analysis: JobAnalysis) -> list[tuple[str, float, str]]:
    """Return weighted, deduplicated job terms used for auditable scoring."""
    fields: list[tuple[str, list[str]]] = [
        ("required_skills", job_analysis.required_skills),
        ("tools_and_stack", job_analysis.tools_and_stack),
        ("domain_focus", job_analysis.domain_focus),
        ("preferred_skills", job_analysis.preferred_skills),
        ("role", [job_analysis.role]),
        ("missions_summary", job_analysis.missions_summary),
    ]

    terms: list[tuple[str, float, str]] = []
    seen: set[str] = set()
    for field_name, values in fields:
        for value in _ordered_unique(values):
            normalized = normalize_relevance_text(value)
            if not normalized or normalized == "unknown" or normalized in seen:
                continue
            seen.add(normalized)
            terms.append((value, _FIELD_WEIGHTS[field_name], field_name))
    return terms


def score_memory_for_job(
    job_analysis: JobAnalysis,
    memory_record: dict[str, Any],
) -> tuple[float, list[str]]:
    """Score one retrieved memory against explicit offer terms and controlled atomic topics."""
    content = str(memory_record.get("content", "")).strip()
    if not content:
        return 0.0, []

    normalized_content = normalize_relevance_text(content)
    content_tokens = _term_tokens(content)
    score = 0.0
    aligned_terms: list[str] = []

    for term, weight, _field_name in job_relevance_terms(job_analysis):
        normalized_term = normalize_relevance_text(term)
        term_tokens = _term_tokens(term)
        if not normalized_term or not term_tokens:
            continue

        exact_match = f" {normalized_term} " in f" {normalized_content} "
        overlap = len(term_tokens & content_tokens)
        coverage = overlap / len(term_tokens)
        semantic_topic_match = _topic_semantically_aligns(memory_record, term)

        if exact_match:
            contribution = weight
        elif overlap and coverage >= 0.60:
            contribution = weight * coverage * 0.65
        elif semantic_topic_match:
            contribution = weight * _SEMANTIC_TOPIC_DISCOUNT
        else:
            continue

        score += contribution
        aligned_terms.append(term)

    return round(score, 3), _ordered_unique(aligned_terms)


def rank_memory_records_for_job(
    job_analysis: JobAnalysis,
    memory_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Attach transparent relevance metadata and rank retrieved memories."""
    scored_records: list[dict[str, Any]] = []
    for retrieval_rank, record in enumerate(memory_records, start=1):
        score, aligned_terms = score_memory_for_job(job_analysis, record)
        enriched = dict(record)
        enriched["relevance_score"] = score
        enriched["aligned_job_terms"] = aligned_terms
        enriched["retrieval_rank"] = retrieval_rank
        scored_records.append(enriched)

    return sorted(
        scored_records,
        key=lambda record: (
            -float(record.get("relevance_score", 0.0)),
            _TYPE_PRIORITY.get(str(record.get("type", "unknown")).casefold(), 6),
            int(record.get("retrieval_rank", 999)),
        ),
    )
