from __future__ import annotations

from typing import TypedDict


class JobCopilotState(TypedDict, total=False):
    job_text: str
    retrieval_query: str
    job_analysis: dict
    retrieved_memories: list[str]
    retrieved_memory_records: list[dict]
    match_insight: dict
    email_draft: dict
