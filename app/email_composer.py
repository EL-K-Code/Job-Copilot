from __future__ import annotations

import hashlib
from collections.abc import Iterable

from app.evidence import validate_grounded_email_draft
from app.relevance import rank_memory_records_for_job
from app.schemas import (
    EmailDraft,
    EmailEvidenceSelection,
    EvidenceBackedClaim,
    JobAnalysis,
)


_MEMORY_TYPE_PRIORITY = (
    "project",
    "experience",
    "skill",
    "education",
    "identity",
    "preference",
    "unknown",
)

_COMPOSITION_VARIANTS = ("direct", "focused", "warm")


def _ensure_sentence(value: str) -> str:
    normalized = " ".join(value.strip().split())
    if not normalized:
        raise ValueError("A selected memory cannot be converted into an empty claim.")
    if normalized[-1] not in ".!?":
        normalized += "."
    return normalized


def memory_to_first_person_claim(content: str) -> str:
    """Convert common candidate-memory wording into conservative first-person prose."""
    normalized = " ".join(str(content).strip().split())
    if not normalized:
        raise ValueError("Profile memory content cannot be empty.")

    lowered = normalized.casefold()
    prefixes = ("the demo candidate ", "the candidate ", "candidate ")
    remainder = normalized
    for prefix in prefixes:
        if lowered.startswith(prefix):
            remainder = normalized[len(prefix) :]
            break
    else:
        return _ensure_sentence(normalized)

    transformations = (
        ("is ", "I am "),
        ("has ", "I have "),
        ("works ", "I work "),
        ("prefers ", "I prefer "),
        ("uses ", "I use "),
        ("was ", "I was "),
    )
    lowered_remainder = remainder.casefold()
    for source, target in transformations:
        if lowered_remainder.startswith(source):
            return _ensure_sentence(target + remainder[len(source) :])

    return _ensure_sentence("I " + remainder[:1].lower() + remainder[1:])


def _record_score(record: dict) -> float:
    try:
        return float(record.get("relevance_score", 0.0))
    except (TypeError, ValueError):
        return 0.0


def validate_memory_selection(
    selection: EmailEvidenceSelection,
    memory_records: list[dict],
) -> None:
    """Reject unknown IDs and weak generic selections when relevant evidence exists."""
    available_records = {
        str(record.get("id", "")).strip(): record
        for record in memory_records
        if str(record.get("id", "")).strip()
        and str(record.get("content", "")).strip()
    }
    unknown_ids = sorted(set(selection.selected_memory_ids) - set(available_records))
    if unknown_ids:
        raise ValueError(
            "Email evidence selection references memories that were not retrieved: "
            f"{unknown_ids}."
        )

    positive_records = [
        record for record in available_records.values() if _record_score(record) > 0
    ]
    if not positive_records:
        return

    selected_records = [available_records[memory_id] for memory_id in selection.selected_memory_ids]
    if not any(_record_score(record) > 0 for record in selected_records):
        raise ValueError(
            "Email evidence selection ignored all memories with explicit offer alignment."
        )

    if len(positive_records) >= len(selected_records) and any(
        _record_score(record) <= 0 for record in selected_records
    ):
        raise ValueError(
            "Email evidence selection included generic evidence while enough explicitly aligned "
            "memories were available."
        )


def _rank_records_if_needed(
    memory_records: list[dict],
    job_analysis: JobAnalysis | None,
) -> list[dict]:
    if job_analysis is None:
        return list(memory_records)
    return rank_memory_records_for_job(job_analysis, memory_records)


def deterministic_fallback_selection(
    memory_records: list[dict],
    *,
    job_analysis: JobAnalysis | None = None,
    limit: int = 3,
) -> EmailEvidenceSelection:
    """Select relevant and type-diverse evidence when model selection fails."""
    if limit < 1:
        raise ValueError("Fallback selection limit must be positive.")

    ranked_records = _rank_records_if_needed(memory_records, job_analysis)
    positive_records = [record for record in ranked_records if _record_score(record) > 0]
    candidates = positive_records or ranked_records

    selected_ids: list[str] = []
    selected_types: set[str] = set()

    # First pass favors evidence-type diversity while preserving relevance order.
    for record in candidates:
        memory_id = str(record.get("id", "")).strip()
        memory_type = str(record.get("type", "unknown")).casefold()
        content = str(record.get("content", "")).strip()
        if not memory_id or not content or memory_id in selected_ids:
            continue
        if memory_type in selected_types:
            continue
        selected_ids.append(memory_id)
        selected_types.add(memory_type)
        if len(selected_ids) >= limit:
            return EmailEvidenceSelection(selected_memory_ids=selected_ids)

    # Second pass fills remaining slots with the strongest unused evidence.
    for record in candidates:
        memory_id = str(record.get("id", "")).strip()
        content = str(record.get("content", "")).strip()
        if not memory_id or not content or memory_id in selected_ids:
            continue
        selected_ids.append(memory_id)
        if len(selected_ids) >= limit:
            return EmailEvidenceSelection(selected_memory_ids=selected_ids)

    if not selected_ids:
        raise ValueError("No valid retrieved memory is available for email composition.")
    return EmailEvidenceSelection(selected_memory_ids=selected_ids)


def _safe_offer_label(value: str, fallback: str) -> str:
    normalized = " ".join(str(value).strip().split())
    if not normalized or normalized.casefold() == "unknown":
        return fallback
    return normalized


def _ordered_unique(values: Iterable[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = " ".join(str(value).strip().split())
        key = normalized.casefold()
        if not normalized or key in seen:
            continue
        seen.add(key)
        output.append(normalized)
    return output


def deterministic_composition_variant(job_analysis: JobAnalysis) -> str:
    """Choose a stable safe template from offer metadata, not candidate facts."""
    key = f"{job_analysis.company}|{job_analysis.role}".encode("utf-8")
    index = hashlib.sha256(key).digest()[0] % len(_COMPOSITION_VARIANTS)
    return _COMPOSITION_VARIANTS[index]


def _opening_for_variant(variant: str, role: str, company: str) -> str:
    templates = {
        "direct": f"I am writing to apply for the {role} at {company}.",
        "focused": f"Please accept my application for the {role} opportunity at {company}.",
        "warm": f"I am pleased to submit my application for the {role} at {company}.",
    }
    return templates[variant]


def _closing_for_variant(variant: str, focus_items: list[str]) -> str:
    if not focus_items:
        templates = {
            "direct": "I would welcome the opportunity to discuss my application.",
            "focused": "I would be glad to discuss how this evidence relates to the role.",
            "warm": "I would appreciate the opportunity to discuss the position further.",
        }
        return templates[variant]

    focus_text = " and ".join(focus_items)
    templates = {
        "direct": (
            f"The role's focus on {focus_text} makes this application particularly relevant. "
            "I would welcome the opportunity to discuss my application."
        ),
        "focused": (
            f"I am particularly interested in the role's work involving {focus_text}. "
            "I would be glad to discuss how the evidence above relates to the position."
        ),
        "warm": (
            f"The opportunity to contribute to work involving {focus_text} is especially "
            "motivating. I would appreciate the opportunity to discuss the position further."
        ),
    }
    return templates[variant]


def compose_grounded_email_draft(
    job_analysis: JobAnalysis,
    selection: EmailEvidenceSelection,
    memory_records: list[dict],
) -> EmailDraft:
    """Build a personalized body from ranked evidence and safe fixed templates."""
    ranked_records = rank_memory_records_for_job(job_analysis, memory_records)
    validate_memory_selection(selection, ranked_records)
    memory_by_id = {str(record["id"]): record for record in ranked_records}

    claim_evidence = [
        EvidenceBackedClaim(
            claim=memory_to_first_person_claim(memory_by_id[memory_id]["content"]),
            supporting_memory_ids=[memory_id],
            relevance_score=_record_score(memory_by_id[memory_id]),
            aligned_job_terms=list(memory_by_id[memory_id].get("aligned_job_terms", [])),
        )
        for memory_id in selection.selected_memory_ids
    ]

    role = _safe_offer_label(job_analysis.role, "advertised position")
    company = _safe_offer_label(job_analysis.company, "your organization")
    subject = f"Application — {role}"
    variant = deterministic_composition_variant(job_analysis)

    evidence_paragraph = " ".join(claim.claim for claim in claim_evidence)
    focus_items = _ordered_unique(
        [*job_analysis.domain_focus, *job_analysis.tools_and_stack]
    )[:2]
    opening = _opening_for_variant(variant, role, company)
    closing = _closing_for_variant(variant, focus_items)

    body = (
        "Dear Hiring Team,\n\n"
        f"{opening}\n\n"
        f"{evidence_paragraph}\n\n"
        f"{closing}\n\n"
        "Kind regards,\n"
        "[Candidate Name]"
    )

    draft = EmailDraft(
        subject=subject,
        body=body,
        tone=selection.tone,
        composition_variant=variant,
        claim_evidence=claim_evidence,
    )
    validate_grounded_email_draft(draft, ranked_records)
    return draft
