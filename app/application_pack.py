from __future__ import annotations

import re
from collections.abc import Iterable

from app.schemas import (
    ApplicationChannel,
    ApplicationPack,
    EmailDraft,
    EvidenceBackedClaim,
    GroundedApplicationText,
    JobAnalysis,
    MatchInsight,
)


_CHANNEL_LABELS: dict[ApplicationChannel, str] = {
    "ats_portal": "Portal or ATS application",
    "email": "Application by email",
    "linkedin": "Recruiter outreach on LinkedIn",
    "academic": "Academic or research application",
    "unknown": "Application route not explicitly stated",
}

_CHANNEL_OUTPUTS: dict[ApplicationChannel, list[str]] = {
    "ats_portal": [
        "cv_tailoring",
        "ats_answers",
        "cover_letter",
        "recruiter_message",
        "interview_prep",
    ],
    "email": [
        "cv_tailoring",
        "application_email",
        "cover_letter",
        "interview_prep",
    ],
    "linkedin": [
        "cv_tailoring",
        "recruiter_message",
        "interview_prep",
    ],
    "academic": [
        "cv_tailoring",
        "cover_letter",
        "application_email",
        "interview_prep",
    ],
    "unknown": [
        "cv_tailoring",
        "ats_answers",
        "cover_letter",
        "recruiter_message",
        "interview_prep",
    ],
}


def _normalize_text(value: str) -> str:
    return " ".join(str(value).strip().split())


def _normalize_term(value: str) -> str:
    text = _normalize_text(value).casefold()
    return re.sub(r"[^a-z0-9+#.]+", " ", text).strip()


def _ordered_unique(values: Iterable[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = _normalize_text(value)
        key = normalized.casefold()
        if not normalized or key in seen:
            continue
        seen.add(key)
        output.append(normalized)
    return output


def _safe_offer_label(value: str, fallback: str) -> str:
    normalized = _normalize_text(value)
    if not normalized or normalized.casefold() == "unknown":
        return fallback
    return normalized


def _safe_candidate_name(value: str | None) -> str:
    normalized = _normalize_text(value or "")
    if normalized.casefold() in {
        "",
        "unknown",
        "candidate name",
        "[candidate name]",
        "local demo",
    }:
        return ""
    return normalized[:120]


def detect_application_channel(
    job_text: str,
    *,
    llm_channel: ApplicationChannel = "unknown",
) -> ApplicationChannel:
    """Conservatively detect an explicitly stated application route.

    Deterministic markers take precedence. The structured-model value is retained only
    when no marker is found, which lets the model capture explicit wording not covered by
    this small ruleset without inventing a route when the offer is silent.
    """

    text = " ".join(str(job_text).casefold().split())

    email_markers = (
        "send your cv to",
        "send your resume to",
        "send your application to",
        "apply by email",
        "application by email",
        "email your application",
        "email your cv",
        "email your resume",
    )
    if any(marker in text for marker in email_markers):
        return "email"
    if re.search(r"\bapply\b.{0,80}\b[\w.+-]+@[\w.-]+\.[a-z]{2,}\b", text):
        return "email"

    linkedin_markers = (
        "linkedin easy apply",
        "apply on linkedin",
        "apply via linkedin",
        "message me on linkedin",
        "contact me on linkedin",
        "reach out on linkedin",
    )
    if any(marker in text for marker in linkedin_markers):
        return "linkedin"

    academic_markers = (
        "statement of purpose",
        "research statement",
        "research proposal",
        "academic transcript",
        "transcripts",
        "letters of recommendation",
        "reference letters",
        "doctoral application",
        "phd application",
        "contact the supervisor",
    )
    if any(marker in text for marker in academic_markers):
        return "academic"

    ats_markers = (
        "easy apply",
        "application form",
        "apply through our careers page",
        "apply on our careers page",
        "apply via our careers page",
        "apply through the portal",
        "apply via the portal",
        "submit your application online",
        "submit an online application",
        "workday",
        "greenhouse",
        "lever.co",
        "smartrecruiters",
    )
    if any(marker in text for marker in ats_markers):
        return "ats_portal"

    return llm_channel if llm_channel in _CHANNEL_LABELS else "unknown"


def recommended_outputs_for_channel(channel: ApplicationChannel) -> list[str]:
    return list(_CHANNEL_OUTPUTS.get(channel, _CHANNEL_OUTPUTS["unknown"]))


def _claims_text(claims: list[EvidenceBackedClaim]) -> str:
    return " ".join(claim.claim for claim in claims)


def _focus_terms(job_analysis: JobAnalysis, *, limit: int = 3) -> list[str]:
    return _ordered_unique(
        [
            *job_analysis.domain_focus,
            *job_analysis.tools_and_stack,
            *job_analysis.required_skills,
        ]
    )[:limit]


def _missing_job_terms(
    job_analysis: JobAnalysis,
    claims: list[EvidenceBackedClaim],
    *,
    limit: int = 10,
) -> list[str]:
    candidate_text = _normalize_term(
        " ".join(
            [
                *(claim.claim for claim in claims),
                *(term for claim in claims for term in claim.aligned_job_terms),
            ]
        )
    )
    missing: list[str] = []
    for term in _ordered_unique(
        [
            *job_analysis.required_skills,
            *job_analysis.tools_and_stack,
            *job_analysis.domain_focus,
        ]
    ):
        normalized_term = _normalize_term(term)
        if not normalized_term:
            continue
        if normalized_term in candidate_text:
            continue
        missing.append(term)
        if len(missing) >= limit:
            break
    return missing


def _cover_letter(
    job_analysis: JobAnalysis,
    claims: list[EvidenceBackedClaim],
    *,
    candidate_name: str | None,
) -> GroundedApplicationText:
    role = _safe_offer_label(job_analysis.role, "advertised position")
    company = _safe_offer_label(job_analysis.company, "your organization")
    focus = _focus_terms(job_analysis, limit=2)
    focus_sentence = (
        f" The role's focus on {' and '.join(focus)} makes this opportunity particularly relevant."
        if focus
        else ""
    )
    name = _safe_candidate_name(candidate_name)
    signature = "Sincerely," + (f"\n{name}" if name else "")
    text = (
        "Dear Hiring Team,\n\n"
        f"I am applying for the {role} at {company}.\n\n"
        f"{_claims_text(claims)}\n\n"
        f"{focus_sentence.strip()} I would welcome the opportunity to discuss how this verified "
        "experience relates to the position.\n\n"
        f"{signature}"
    )
    return GroundedApplicationText(
        title="Cover letter",
        text=text,
        claim_evidence=list(claims),
    )


def _ats_answers(
    job_analysis: JobAnalysis,
    claims: list[EvidenceBackedClaim],
) -> list[GroundedApplicationText]:
    role = _safe_offer_label(job_analysis.role, "role")
    company = _safe_offer_label(job_analysis.company, "the organization")
    claims_text = _claims_text(claims)
    focus = _focus_terms(job_analysis, limit=2)
    focus_text = " and ".join(focus)

    fit_suffix = (
        f" The position explicitly emphasizes {focus_text}, which is why these verified points "
        "are the most relevant parts of my profile to highlight."
        if focus_text
        else ""
    )
    return [
        GroundedApplicationText(
            title="Why are you a good fit for this role?",
            text=(
                f"My fit for the {role} at {company} is grounded in the following verified "
                f"experience: {claims_text}{fit_suffix}"
            ),
            claim_evidence=list(claims),
        ),
        GroundedApplicationText(
            title="Describe your most relevant experience.",
            text=claims_text,
            claim_evidence=list(claims),
        ),
    ]


def _recruiter_message(
    job_analysis: JobAnalysis,
    claims: list[EvidenceBackedClaim],
) -> GroundedApplicationText:
    role = _safe_offer_label(job_analysis.role, "role")
    company = _safe_offer_label(job_analysis.company, "your organization")
    selected_claims = claims[:1]
    claim_text = _claims_text(selected_claims)
    text = (
        f"Hello, I came across the {role} opportunity at {company}. {claim_text} "
        "I would be glad to connect and learn more about the role."
    )
    return GroundedApplicationText(
        title="Recruiter outreach message",
        text=text[:600].rstrip(),
        claim_evidence=list(selected_claims),
    )


def _interview_questions(
    job_analysis: JobAnalysis,
    missing_terms: list[str],
) -> list[str]:
    questions: list[str] = []
    for term in _ordered_unique(
        [*job_analysis.required_skills, *job_analysis.tools_and_stack]
    )[:4]:
        questions.append(
            f"Can you describe a concrete example of work related to {term}?"
        )
    for mission in _ordered_unique(job_analysis.missions_summary)[:2]:
        questions.append(f"How would you approach this responsibility: {mission}?")
    for term in missing_terms[:2]:
        questions.append(
            f"The offer mentions {term}. How would you address this requirement honestly?"
        )
    return _ordered_unique(questions)[:8]


def compose_application_pack(
    *,
    job_analysis: JobAnalysis,
    match_insight: MatchInsight,
    email_draft: EmailDraft,
    candidate_name: str | None = None,
) -> ApplicationPack:
    """Build all application outputs from the email's already-validated claim ledger.

    This function performs no LLM call. Candidate facts are reused verbatim from the
    grounded email ledger, while offer terms are used only for route guidance, gap review
    and interview preparation.
    """

    del match_insight  # The deterministic pack relies on the validated claim ledger.
    claims = list(email_draft.claim_evidence)
    if not claims:
        raise ValueError("An application pack requires at least one grounded candidate claim.")

    channel = job_analysis.application_channel
    missing_terms = _missing_job_terms(job_analysis, claims)
    return ApplicationPack(
        channel=channel,
        route_label=_CHANNEL_LABELS[channel],
        recommended_outputs=recommended_outputs_for_channel(channel),
        cv_highlights=claims,
        missing_job_terms=missing_terms,
        ats_answers=_ats_answers(job_analysis, claims),
        cover_letter=_cover_letter(
            job_analysis,
            claims,
            candidate_name=candidate_name,
        ),
        recruiter_message=_recruiter_message(job_analysis, claims),
        interview_questions=_interview_questions(job_analysis, missing_terms),
        application_email=email_draft,
    )
