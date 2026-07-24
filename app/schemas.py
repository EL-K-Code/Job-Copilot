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
