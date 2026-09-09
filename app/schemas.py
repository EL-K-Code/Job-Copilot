from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


ApplicationChannel = Literal[
    "ats_portal",
    "email",
    "linkedin",
    "academic",
    "unknown",
]
ApplicationOutput = Literal[
    "cv_tailoring",
    "ats_answers",
    "cover_letter",
    "recruiter_message",
    "application_email",
    "interview_prep",
]
ApplicationWorkflowStage = Literal[
    "discovered",
    "analyzed",
    "ready_to_apply",
    "awaiting_approval",
    "applied",
    "follow_up_due",
    "interview",
    "rejected",
    "offer",
    "closed",
]
ApplicationWorkflowActor = Literal["user", "agent", "system"]


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
    application_channel: ApplicationChannel = Field(
        default="unknown",
        description=(
            "Explicit application route stated in the offer. Use ats_portal for a careers "
            "page, form, Easy Apply or ATS; email for an explicit application email route; "
            "linkedin for explicit LinkedIn outreach; academic for research or academic "
            "submission instructions; otherwise unknown."
        ),
    )
    application_instructions: list[str] = Field(
        default_factory=list,
        description="Explicit instructions explaining how the candidate should apply.",
    )
    requested_materials: list[str] = Field(
        default_factory=list,
        description=(
            "Materials explicitly requested, such as CV, cover letter, portfolio, references, "
            "transcript, research statement or short-answer responses."
        ),
    )


class EvidenceBackedClaim(BaseModel):
    claim: str = Field(
        description=(
            "A conservative factual candidate claim that can be copied into an application "
            "output without adding strength, ownership, scale, recency, or production context."
        )
    )
    supporting_memory_ids: list[str] = Field(
        min_length=1,
        description="IDs of retrieved profile memories that directly support the claim.",
    )
    relevance_score: float = Field(
        default=0.0,
        ge=0.0,
        description="Deterministic offer-to-memory relevance score used for selection audit.",
    )
    aligned_job_terms: list[str] = Field(
        default_factory=list,
        description="Explicit offer terms that matched the supporting memory.",
    )

    @field_validator("claim")
    @classmethod
    def validate_claim(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Evidence-backed claim text cannot be empty.")
        return normalized

    @field_validator("supporting_memory_ids", "aligned_job_terms")
    @classmethod
    def normalize_string_lists(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(item.strip() for item in value if item.strip()))

    @field_validator("supporting_memory_ids")
    @classmethod
    def validate_supporting_memory_ids(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("Evidence-backed claims require at least one memory ID.")
        return value


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
            "These claims form the factual evidence plan for application outputs."
        ),
    )


class EmailEvidenceSelection(BaseModel):
    selected_memory_ids: list[str] = Field(
        min_length=1,
        max_length=3,
        description=(
            "One to three retrieved memory IDs containing the strongest directly relevant "
            "candidate evidence for the application pack."
        ),
    )
    tone: Literal["professional", "warm", "concise", "premium"] = Field(
        default="professional",
        description="Tone used by deterministic application composers.",
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
    composition_variant: Literal["direct", "focused", "warm"] = Field(
        default="direct",
        description=(
            "Deterministically selected safe template variant. It changes only non-factual "
            "opening and closing prose."
        ),
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


class GroundedApplicationText(BaseModel):
    title: str = Field(description="User-facing label for this application output.")
    text: str = Field(description="Editable deterministic application text.")
    claim_evidence: list[EvidenceBackedClaim] = Field(
        default_factory=list,
        description=(
            "Evidence ledger for factual candidate claims included in this specific output. "
            "Offer-only or procedural wording does not require candidate evidence."
        ),
    )

    @field_validator("title", "text")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Application output title and text cannot be empty.")
        return normalized


class ApplicationPack(BaseModel):
    channel: ApplicationChannel = "unknown"
    route_label: str = Field(description="Plain-language description of the recommended route.")
    recommended_outputs: list[ApplicationOutput] = Field(default_factory=list)
    cv_highlights: list[EvidenceBackedClaim] = Field(default_factory=list)
    missing_job_terms: list[str] = Field(
        default_factory=list,
        description=(
            "Explicit job terms not covered by the selected verified claims. These are gaps or "
            "review prompts and must never be presented as candidate skills."
        ),
    )
    ats_answers: list[GroundedApplicationText] = Field(default_factory=list)
    cover_letter: GroundedApplicationText
    recruiter_message: GroundedApplicationText
    interview_questions: list[str] = Field(default_factory=list)
    application_email: EmailDraft

    @field_validator("route_label")
    @classmethod
    def validate_route_label(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Application route label cannot be empty.")
        return normalized

    @field_validator("recommended_outputs", "missing_job_terms", "interview_questions")
    @classmethod
    def normalize_pack_lists(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(str(item).strip() for item in value if str(item).strip()))


class ApplicationWorkflowEvent(BaseModel):
    event_type: str = Field(description="Machine-readable lifecycle or action event type.")
    stage: ApplicationWorkflowStage = Field(description="Workflow stage after the event.")
    actor: ApplicationWorkflowActor = Field(default="system")
    occurred_at: str = Field(description="UTC ISO timestamp for the event.")
    detail: str = Field(default="", description="Human-readable event detail without secrets.")
    action_key: str = Field(
        default="",
        description="Optional deterministic idempotency key for external actions.",
    )

    @field_validator("event_type")
    @classmethod
    def validate_event_type(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Workflow event_type cannot be empty.")
        return normalized

    @field_validator("occurred_at")
    @classmethod
    def validate_occurred_at(cls, value: str) -> str:
        normalized = value.strip()
        try:
            datetime.fromisoformat(normalized)
        except ValueError as exc:
            raise ValueError("occurred_at must be a valid ISO datetime.") from exc
        return normalized


class ApplicationRecord(BaseModel):
    company: str = Field(description="Company name.")
    role: str = Field(description="Role or job title.")
    status: Literal["drafted", "applied", "interview", "follow_up", "closed"] = Field(
        default="drafted",
        description="Legacy tracker status kept for backward compatibility.",
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
    application_id: str = Field(
        default="",
        description="Stable opaque identifier assigned to new workflow records.",
    )
    workflow_stage: ApplicationWorkflowStage | None = Field(
        default=None,
        description=(
            "Agentic lifecycle stage. Older records may omit this field and are mapped "
            "from the legacy tracker status at read time."
        ),
    )
    application_channel: ApplicationChannel = Field(
        default="unknown",
        description="Application route extracted from the job offer.",
    )
    workflow_history: list[ApplicationWorkflowEvent] = Field(
        default_factory=list,
        description="Append-only human-readable lifecycle and external-action audit trail.",
    )
    external_action_keys: list[str] = Field(
        default_factory=list,
        description="Successful external-action idempotency keys; never contains OAuth credentials.",
    )
    updated_at: str = Field(
        default="",
        description="Last workflow mutation timestamp in ISO format.",
    )

    @field_validator("company", "role", "source")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Required application text fields cannot be empty.")
        return normalized

    @field_validator("application_id")
    @classmethod
    def normalize_application_id(cls, value: str) -> str:
        return value.strip()

    @field_validator("external_action_keys")
    @classmethod
    def normalize_action_keys(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(item.strip() for item in value if item.strip()))

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

    @field_validator("created_at", "updated_at")
    @classmethod
    def validate_iso_timestamp(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            return ""
        try:
            datetime.fromisoformat(normalized)
        except ValueError as exc:
            raise ValueError("Application timestamps must be valid ISO datetimes.") from exc
        return normalized
