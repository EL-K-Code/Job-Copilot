from __future__ import annotations

from collections.abc import Iterable

from app.evidence import validate_grounded_email_draft
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


def validate_memory_selection(
    selection: EmailEvidenceSelection,
    memory_records: list[dict[str, str]],
) -> None:
    """Reject selections that do not point to retrieved, non-empty memories."""
    available_ids = {
        record["id"]
        for record in memory_records
        if record.get("id") and record.get("content", "").strip()
    }
    unknown_ids = sorted(set(selection.selected_memory_ids) - available_ids)
    if unknown_ids:
        raise ValueError(
            "Email evidence selection references memories that were not retrieved: "
            f"{unknown_ids}."
        )


def deterministic_fallback_selection(
    memory_records: list[dict[str, str]],
    *,
    limit: int = 3,
) -> EmailEvidenceSelection:
    """Select the strongest retrieved evidence deterministically when LLM selection fails."""
    if limit < 1:
        raise ValueError("Fallback selection limit must be positive.")

    selected_ids: list[str] = []
    for memory_type in _MEMORY_TYPE_PRIORITY:
        for record in memory_records:
            if record.get("type", "unknown").casefold() != memory_type:
                continue
            memory_id = record.get("id", "").strip()
            content = record.get("content", "").strip()
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


def compose_grounded_email_draft(
    job_analysis: JobAnalysis,
    selection: EmailEvidenceSelection,
    memory_records: list[dict[str, str]],
) -> EmailDraft:
    """Build the final body only from selected memories and fixed non-factual prose."""
    validate_memory_selection(selection, memory_records)
    memory_by_id = {record["id"]: record for record in memory_records}

    claim_evidence = [
        EvidenceBackedClaim(
            claim=memory_to_first_person_claim(memory_by_id[memory_id]["content"]),
            supporting_memory_ids=[memory_id],
        )
        for memory_id in selection.selected_memory_ids
    ]

    role = _safe_offer_label(job_analysis.role, "advertised position")
    company = _safe_offer_label(job_analysis.company, "your organization")
    subject = f"Application — {role}"

    evidence_paragraph = " ".join(claim.claim for claim in claim_evidence)
    focus_items = _ordered_unique(
        [*job_analysis.domain_focus, *job_analysis.tools_and_stack]
    )[:2]
    if focus_items:
        focus_text = " and ".join(focus_items)
        closing = (
            f"The role's focus on {focus_text} makes this application particularly relevant. "
            "I would welcome the opportunity to discuss my application."
        )
    else:
        closing = "I would welcome the opportunity to discuss my application."

    body = (
        "Dear Hiring Team,\n\n"
        f"I am writing to apply for the {role} at {company}.\n\n"
        f"{evidence_paragraph}\n\n"
        f"{closing}\n\n"
        "Kind regards,\n"
        "[Candidate Name]"
    )

    draft = EmailDraft(
        subject=subject,
        body=body,
        tone=selection.tone,
        claim_evidence=claim_evidence,
    )
    validate_grounded_email_draft(draft, memory_records)
    return draft
