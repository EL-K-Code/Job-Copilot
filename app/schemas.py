from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class JobAnalysis(BaseModel):
    company: str = Field(
        default="Unknown",
        description="Name of the company posting the job offer.",
    )
    role: str = Field(
        default="Unknown",
        description="Job title or internship title.",
    )
    location: str = Field(
        default="Unknown",
        description="Location of the role.",
    )
    contract_type: str = Field(
        default="Unknown",
        description="Type of contract such as internship, full-time, apprenticeship, or freelance.",
    )
    start_date: str = Field(
        default="Unknown",
        description="Expected start date if mentioned in the job offer.",
    )
    missions_summary: list[str] = Field(
        default_factory=list,
        description="Short summary of the main missions or responsibilities.",
    )
    required_skills: list[str] = Field(
        default_factory=list,
        description="Technical or business skills explicitly required in the offer.",
    )
    preferred_skills: list[str] = Field(
        default_factory=list,
        description="Nice-to-have or bonus skills mentioned in the offer.",
    )
    tools_and_stack: list[str] = Field(
        default_factory=list,
        description="Technologies, frameworks, APIs, or tools explicitly mentioned.",
    )
    profile_summary: str = Field(
        default="",
        description="Short summary of the type of candidate the company is looking for.",
    )
    domain_focus: list[str] = Field(
        default_factory=list,
        description="Main themes or domains of the role, such as RAG, agentic AI, NLP, MLOps, or product analytics.",
    )
    key_highlights_for_candidate: list[str] = Field(
        default_factory=list,
        description="The most important points a candidate should highlight to match this role.",
    )


class EvidenceBackedClaim(BaseModel):
    claim: str = Field(
        description=(
            "A conservative factual candidate claim that can be copied into the email "
            "without adding strength, ownership, scale, recency, or production context."
        )
    )
    supporting_memory_ids: list[str] = Field(
        min_length=1,
        description="IDs of retrieved profile memories that directly support the claim.",
    )

    @field_validator("claim")
    @classmethod
    def validate_claim(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Evidence-backed claim text cannot be empty.")
        return normalized

    @field_validator("supporting_memory_ids")
    @classmethod
    def validate_supporting_memory_ids(cls, value: list[str]) -> list[str]:
        normalized = list(dict.fromkeys(item.strip() for item in value if item.strip()))
        if not normalized:
            raise ValueError("Evidence-backed claims require at least one memory ID.")
        return normalized


class MatchInsight(BaseModel):
    strengths: list[str] = Field(
        default_factory=list,
        description="Strong matching points between the candidate profile and the job.",
    )
    gaps: list[str] = Field(
        default_factory=list,
        description="Potential missing points or weaker areas relative to the job.",
    )
    suggested_angles: list[str] = Field(
        default_factory=list,
        description="Recommended positioning angles to use in the application.",
    )
    relevant_profile_memories: list[str] = Field(
        default_factory=list,
        description="Relevant memories retrieved from the candidate profile.",
    )
    supported_claims: list[EvidenceBackedClaim] = Field(
        default_factory=list,
        description=(
            "Candidate claims that are directly supported by identified retrieved memories. "
            "These claims form the factual evidence plan for email generation."
        ),
    )


class EmailEvidenceSelection(BaseModel):
    selected_memory_ids: list[str] = Field(
        min_length=1,
        max_length=3,
        description=(
            "One to three retrieved memory IDs containing the strongest directly relevant "
            "candidate evidence for the application email."
        ),
    )
    tone: Literal["professional", "warm", "concise", "premium"] = Field(
        default="professional",
        description="Tone used by the deterministic email composer.",
    )

    @field_validator("selected_memory_ids")
    @classmethod
    def validate_selected_memory_ids(cls, value: list[str]) -> list[str]:
        normalized = list(dict.fromkeys(item.strip() for item in value if item.strip()))
        if not normalized:
            raise ValueError("At least one retrieved memory ID must be selected.")
        if len(normalized) > 3:
            raise ValueError("No more than three retrieved memory IDs may be selected.")
        return normalized


class EmailDraft(BaseModel):
    subject: str = Field(
        default="",
        description="Email subject line.",
    )
    body: str = Field(
        default="",
        description="Full email body.",
    )
    tone: Literal["professional", "warm", "concise", "premium"] = Field(
        default="professional",
        description="Tone used in the email.",
    )
    claim_evidence: list[EvidenceBackedClaim] = Field(
        default_factory=list,
        description=(
            "Complete audit ledger for factual candidate claims in the email. The body is "
            "constructed deterministically from this ledger so no hidden candidate claim can "
            "be added outside it."
        ),
    )

    @field_validator("subject")
    @classmethod
    def validate_subject(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Email subject cannot be empty.")
        if "\r" in normalized or "\n" in normalized:
            raise ValueError("Email subject cannot contain newline characters.")
        return normalized

    @field_validator("body")
    @classmethod
    def validate_body(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Email body cannot be empty.")
        return value.strip()


class ApplicationRecord(BaseModel):
    company: str = Field(description="Company name.")
    role: str = Field(description="Role or job title.")
    status: Literal["drafted", "applied", "interview", "follow_up", "closed"] = Field(
        default="drafted",
        description="Current application status.",
    )
    source: str = Field(
        default="manual",
        description="Where the job opportunity came from.",
    )
    notes: str = Field(
        default="",
        description="Free notes about this application.",
    )
    reminder_date: str = Field(
        default="",
        description="Optional reminder date in YYYY-MM-DD format.",
    )
    email_subject: str = Field(
        default="",
        description="Generated application email subject.",
    )
    email_body: str = Field(
        default="",
        description="Generated application email body.",
    )
    created_at: str = Field(
        default="",
        description="Creation timestamp in ISO format.",
    )

    @field_validator("company", "role", "source")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Required application text fields cannot be empty.")
        return normalized

    @field_validator("reminder_date")
    @classmethod
    def validate_reminder_date(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            return ""
        try:
            datetime.strptime(normalized, "%Y-%m-%d")
        except ValueError as exc:
            raise ValueError("reminder_date must use the YYYY-MM-DD format.") from exc
        return normalized

    @field_validator("created_at")
    @classmethod
    def validate_created_at(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            return ""
        try:
            datetime.fromisoformat(normalized)
        except ValueError as exc:
            raise ValueError("created_at must be a valid ISO datetime.") from exc
        return normalized
