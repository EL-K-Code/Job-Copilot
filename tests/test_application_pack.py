from __future__ import annotations

from app.application_pack import (
    compose_application_pack,
    detect_application_channel,
    recommended_outputs_for_channel,
)
from app.schemas import (
    EmailDraft,
    EvidenceBackedClaim,
    JobAnalysis,
    MatchInsight,
)


def _claim(
    text: str,
    memory_id: str,
    *,
    aligned: list[str] | None = None,
) -> EvidenceBackedClaim:
    return EvidenceBackedClaim(
        claim=text,
        supporting_memory_ids=[memory_id],
        relevance_score=5.0,
        aligned_job_terms=aligned or [],
    )


def _email(claims: list[EvidenceBackedClaim]) -> EmailDraft:
    return EmailDraft(
        subject="Application — AI Engineer",
        body=(
            "Dear Hiring Team,\n\nI am applying for the AI Engineer role.\n\n"
            + " ".join(claim.claim for claim in claims)
            + "\n\nKind regards,\nAlex"
        ),
        claim_evidence=claims,
    )


def test_deterministic_channel_detection_uses_explicit_routes():
    assert (
        detect_application_channel("Please send your CV to jobs@example.com")
        == "email"
    )
    assert detect_application_channel("Apply through our Workday portal") == "ats_portal"
    assert detect_application_channel("Message me on LinkedIn to apply") == "linkedin"
    assert (
        detect_application_channel(
            "Submit a research statement, academic transcript and reference letters."
        )
        == "academic"
    )
    assert detect_application_channel("We are hiring an AI Engineer") == "unknown"


def test_email_marker_takes_precedence_over_generic_portal_wording():
    text = "Read the careers page, then send your application to jobs@example.com."
    assert detect_application_channel(text, llm_channel="ats_portal") == "email"


def test_channel_recommendations_keep_email_optional():
    assert "application_email" in recommended_outputs_for_channel("email")
    assert "application_email" not in recommended_outputs_for_channel("ats_portal")
    assert "ats_answers" in recommended_outputs_for_channel("ats_portal")
    assert "recruiter_message" in recommended_outputs_for_channel("linkedin")


def test_application_pack_reuses_only_validated_claims():
    claims = [
        _claim(
            "I built an agentic workflow with LangGraph.",
            "project_langgraph",
            aligned=["LangGraph", "agentic workflows"],
        ),
        _claim(
            "I work with Python and FastAPI.",
            "skill_python_fastapi",
            aligned=["Python", "FastAPI"],
        ),
    ]
    analysis = JobAnalysis(
        company="Example AI",
        role="AI Engineer",
        application_channel="ats_portal",
        required_skills=["Python", "Kubernetes"],
        tools_and_stack=["FastAPI", "LangGraph", "Kubernetes"],
        domain_focus=["agentic AI"],
        missions_summary=["Build reliable AI services"],
    )

    pack = compose_application_pack(
        job_analysis=analysis,
        match_insight=MatchInsight(),
        email_draft=_email(claims),
        candidate_name="Komla Alex LABOU",
    )

    assert pack.channel == "ats_portal"
    assert pack.route_label == "Portal or ATS application"
    assert [item.claim for item in pack.cv_highlights] == [
        claim.claim for claim in claims
    ]
    assert "Kubernetes" in pack.missing_job_terms
    assert "I use Kubernetes" not in pack.cover_letter.text
    assert "I use Kubernetes" not in " ".join(
        answer.text for answer in pack.ats_answers
    )
    assert "Komla Alex LABOU" in pack.cover_letter.text

    for claim in claims:
        assert claim.claim in pack.cover_letter.text
        assert claim.claim in pack.ats_answers[0].text
        assert claim.claim in pack.ats_answers[1].text

    assert pack.recruiter_message.claim_evidence == [claims[0]]
    assert claims[0].claim in pack.recruiter_message.text
    assert claims[1].claim not in pack.recruiter_message.text


def test_missing_terms_are_advisory_not_candidate_evidence():
    claim = _claim("I use Python.", "skill_python", aligned=["Python"])
    pack = compose_application_pack(
        job_analysis=JobAnalysis(
            company="Example",
            role="ML Engineer",
            required_skills=["Python", "AWS"],
            application_channel="unknown",
        ),
        match_insight=MatchInsight(gaps=["AWS is not evidenced."],),
        email_draft=_email([claim]),
    )

    assert pack.missing_job_terms == ["AWS"]
    assert pack.cv_highlights[0].supporting_memory_ids == ["skill_python"]
    assert all(
        evidence.supporting_memory_ids == ["skill_python"]
        for answer in pack.ats_answers
        for evidence in answer.claim_evidence
    )
