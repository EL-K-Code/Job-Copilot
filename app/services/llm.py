from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.email_composer import (
    compose_grounded_email_draft,
    deterministic_fallback_selection,
    validate_memory_selection,
)
from app.evidence import normalize_memory_records, validate_claim_evidence
from app.prompts import (
    EMAIL_DRAFT_SYSTEM_PROMPT,
    JOB_ANALYSIS_SYSTEM_PROMPT,
    JOB_MATCH_SYSTEM_PROMPT,
)
from app.relevance import rank_memory_records_for_job
from app.schemas import (
    EmailDraft,
    EmailEvidenceSelection,
    JobAnalysis,
    MatchInsight,
)
from app.services.model_provider import get_structured_chat_model


logger = logging.getLogger(__name__)
MemoryInput = dict[str, Any] | str


def get_job_analysis_llm():
    return get_structured_chat_model(JobAnalysis)


def get_match_insight_llm():
    return get_structured_chat_model(MatchInsight)


def get_email_evidence_selection_llm():
    return get_structured_chat_model(EmailEvidenceSelection)


def get_email_draft_llm():
    """Backward-compatible alias for the evidence-selection model."""
    return get_email_evidence_selection_llm()


def analyze_job_offer(job_text: str) -> JobAnalysis:
    if not job_text.strip():
        raise ValueError("The job offer text cannot be empty.")

    structured_llm = get_job_analysis_llm()
    messages = [
        SystemMessage(content=JOB_ANALYSIS_SYSTEM_PROMPT),
        HumanMessage(content=f"Job offer:\n{job_text}"),
    ]
    return structured_llm.invoke(messages)


def generate_match_insight(
    job_analysis: JobAnalysis,
    retrieved_profile_memories: list[MemoryInput],
) -> MatchInsight:
    structured_llm = get_match_insight_llm()
    memory_records = normalize_memory_records(retrieved_profile_memories)

    messages = [
        SystemMessage(content=JOB_MATCH_SYSTEM_PROMPT),
        HumanMessage(
            content=(
                "Job analysis:\n"
                f"{json.dumps(job_analysis.model_dump(), indent=2)}\n\n"
                "Retrieved profile-memory records:\n"
                f"{json.dumps(memory_records, indent=2)}"
            )
        ),
    ]

    result = structured_llm.invoke(messages)
    try:
        validate_claim_evidence(result.supported_claims, memory_records)
    except ValueError as first_error:
        repair_message = HumanMessage(
            content=(
                "The previous structured match failed deterministic evidence validation. "
                "Regenerate it using only retrieved memory IDs and narrower claims.\n\n"
                f"Validation error: {first_error}\n\n"
                "Previous match:\n"
                f"{json.dumps(result.model_dump(), indent=2)}"
            )
        )
        result = structured_llm.invoke([*messages, repair_message])
        try:
            validate_claim_evidence(result.supported_claims, memory_records)
        except ValueError as second_error:
            raise RuntimeError(
                "The profile-to-job match could not satisfy the evidence contract after "
                "one repair attempt."
            ) from second_error
    return result


def _select_email_evidence(
    job_analysis: JobAnalysis,
    match_insight: MatchInsight,
    memory_records: list[dict[str, Any]],
) -> EmailEvidenceSelection:
    """Select from auditable relevance-ranked memories, with a safe fallback."""
    structured_llm = get_email_evidence_selection_llm()
    ranked_records = rank_memory_records_for_job(job_analysis, memory_records)
    messages = [
        SystemMessage(content=EMAIL_DRAFT_SYSTEM_PROMPT),
        HumanMessage(
            content=(
                "Select the strongest and most role-specific retrieved evidence for a concise "
                "application email. Use relevance_score and aligned_job_terms as deterministic "
                "audit signals, while checking the underlying memory content.\n\n"
                "Job analysis:\n"
                f"{json.dumps(job_analysis.model_dump(), indent=2)}\n\n"
                "Match insight:\n"
                f"{json.dumps(match_insight.model_dump(), indent=2)}\n\n"
                "Relevance-ranked profile-memory records:\n"
                f"{json.dumps(ranked_records, indent=2)}"
            )
        ),
    ]

    try:
        selection = structured_llm.invoke(messages)
        validate_memory_selection(selection, ranked_records)
        return selection
    except Exception as first_error:  # Structured-output and validation failures.
        repair_message = HumanMessage(
            content=(
                "The previous evidence selection was invalid. Return only one to three IDs "
                "that appear exactly in the ranked memory records. Prefer positive relevance "
                "scores, explicit aligned_job_terms and evidence-type diversity. Do not write "
                "claims or email prose.\n\n"
                f"Selection error: {first_error}"
            )
        )
        try:
            selection = structured_llm.invoke([*messages, repair_message])
            validate_memory_selection(selection, ranked_records)
            return selection
        except Exception as second_error:
            logger.warning(
                "Email evidence selection failed twice; using deterministic relevance-aware "
                "fallback. Error: %s",
                second_error,
            )
            return deterministic_fallback_selection(
                ranked_records,
                job_analysis=job_analysis,
            )


def generate_application_email_draft(
    job_analysis: JobAnalysis,
    match_insight: MatchInsight,
    retrieved_profile_memories: list[MemoryInput] | None = None,
) -> EmailDraft:
    memory_source: list[MemoryInput] = (
        retrieved_profile_memories
        if retrieved_profile_memories is not None
        else list(match_insight.relevant_profile_memories)
    )
    memory_records = normalize_memory_records(memory_source)
    selection = _select_email_evidence(job_analysis, match_insight, memory_records)
    return compose_grounded_email_draft(
        job_analysis=job_analysis,
        selection=selection,
        memory_records=memory_records,
    )
