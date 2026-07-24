from __future__ import annotations

import json
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from app.config import settings
from app.evidence import (
    normalize_memory_records,
    validate_claim_evidence,
    validate_grounded_email_draft,
)
from app.prompts import (
    JOB_ANALYSIS_SYSTEM_PROMPT,
    JOB_MATCH_SYSTEM_PROMPT,
    EMAIL_DRAFT_SYSTEM_PROMPT,
)
from app.schemas import JobAnalysis, MatchInsight, EmailDraft


MemoryInput = dict[str, Any] | str


def get_base_llm() -> ChatAnthropic:
    return ChatAnthropic(
        model=settings.anthropic_model,
        temperature=0,
        api_key=settings.require_anthropic_api_key(),
    )


def get_job_analysis_llm():
    llm = get_base_llm()
    return llm.with_structured_output(JobAnalysis)


def get_match_insight_llm():
    llm = get_base_llm()
    return llm.with_structured_output(MatchInsight)


def get_email_draft_llm():
    llm = get_base_llm()
    return llm.with_structured_output(EmailDraft)


def analyze_job_offer(job_text: str) -> JobAnalysis:
    if not job_text.strip():
        raise ValueError("The job offer text cannot be empty.")

    structured_llm = get_job_analysis_llm()

    messages = [
        SystemMessage(content=JOB_ANALYSIS_SYSTEM_PROMPT),
        HumanMessage(content=f"Job offer:\n{job_text}"),
    ]

    result = structured_llm.invoke(messages)
    return result


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


def generate_application_email_draft(
    job_analysis: JobAnalysis,
    match_insight: MatchInsight,
    retrieved_profile_memories: list[MemoryInput] | None = None,
) -> EmailDraft:
    structured_llm = get_email_draft_llm()
    memory_source: list[MemoryInput] = (
        retrieved_profile_memories
        if retrieved_profile_memories is not None
        else list(match_insight.relevant_profile_memories)
    )
    memory_records = normalize_memory_records(memory_source)

    messages = [
        SystemMessage(content=EMAIL_DRAFT_SYSTEM_PROMPT),
        HumanMessage(
            content=(
                "Write a job application email draft based on the following information.\n\n"
                "Job analysis:\n"
                f"{json.dumps(job_analysis.model_dump(), indent=2)}\n\n"
                "Match insight and approved factual claim plan:\n"
                f"{json.dumps(match_insight.model_dump(), indent=2)}\n\n"
                "Retrieved profile-memory records:\n"
                f"{json.dumps(memory_records, indent=2)}\n\n"
                "Use a premium professional tone, but preserve the exact strength and scope "
                "of the evidence."
            )
        ),
    ]

    result = structured_llm.invoke(messages)
    try:
        validate_grounded_email_draft(result, memory_records)
    except ValueError as first_error:
        repair_message = HumanMessage(
            content=(
                "The previous draft failed deterministic grounding validation. Regenerate "
                "a more conservative email. Every claim_evidence claim must be clearly and "
                "locally represented in one body sentence, using the same material facts and "
                "only directly supporting retrieved memory IDs. Harmless grammatical "
                "rephrasing is allowed; stronger scope, ownership or proficiency is not.\n\n"
                f"Validation error: {first_error}\n\n"
                "Previous draft:\n"
                f"{json.dumps(result.model_dump(), indent=2)}"
            )
        )
        result = structured_llm.invoke([*messages, repair_message])
        try:
            validate_grounded_email_draft(result, memory_records)
        except ValueError as second_error:
            raise RuntimeError(
                "The email draft could not satisfy the grounding contract after one repair "
                "attempt."
            ) from second_error
    return result
