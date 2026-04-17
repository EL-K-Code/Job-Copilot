from __future__ import annotations

import json

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from app.config import settings
from app.prompts import (
    JOB_ANALYSIS_SYSTEM_PROMPT,
    JOB_MATCH_SYSTEM_PROMPT,
    EMAIL_DRAFT_SYSTEM_PROMPT,
)
from app.schemas import JobAnalysis, MatchInsight, EmailDraft


def get_base_llm() -> ChatAnthropic:
    return ChatAnthropic(
        model=settings.anthropic_model,
        temperature=0,
        api_key=settings.anthropic_api_key,
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
    structured_llm = get_job_analysis_llm()

    messages = [
        SystemMessage(content=JOB_ANALYSIS_SYSTEM_PROMPT),
        HumanMessage(content=f"Job offer:\n{job_text}")
    ]

    result = structured_llm.invoke(messages)
    return result


def generate_match_insight(
    job_analysis: JobAnalysis,
    retrieved_profile_memories: list[str],
) -> MatchInsight:
    structured_llm = get_match_insight_llm()

    messages = [
        SystemMessage(content=JOB_MATCH_SYSTEM_PROMPT),
        HumanMessage(
            content=(
                "Job analysis:\n"
                f"{json.dumps(job_analysis.model_dump(), indent=2)}\n\n"
                "Retrieved profile memories:\n"
                f"{json.dumps(retrieved_profile_memories, indent=2)}"
            )
        ),
    ]

    result = structured_llm.invoke(messages)
    return result


def generate_application_email_draft(
    job_analysis: JobAnalysis,
    match_insight: MatchInsight,
) -> EmailDraft:
    structured_llm = get_email_draft_llm()

    messages = [
        SystemMessage(content=EMAIL_DRAFT_SYSTEM_PROMPT),
        HumanMessage(
            content=(
                "Write a job application email draft based on the following information.\n\n"
                "Job analysis:\n"
                f"{json.dumps(job_analysis.model_dump(), indent=2)}\n\n"
                "Match insight:\n"
                f"{json.dumps(match_insight.model_dump(), indent=2)}\n\n"
                "Use a premium professional tone."
            )
        ),
    ]

    result = structured_llm.invoke(messages)
    return result