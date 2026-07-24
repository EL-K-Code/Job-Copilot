import pytest

from app.evidence import (
    normalize_memory_records,
    validate_claim_evidence,
    validate_grounded_email_draft,
)
from app.prompts import EMAIL_DRAFT_SYSTEM_PROMPT, JOB_MATCH_SYSTEM_PROMPT
from app.schemas import EmailDraft, EvidenceBackedClaim


MEMORIES = [
    {
        "id": "project_1",
        "type": "project",
        "content": "The candidate built an agentic workflow with LangGraph.",
    },
    {
        "id": "skill_1",
        "type": "skill",
        "content": "The candidate works with Python and FastAPI.",
    },
]


def test_memory_records_preserve_ids_and_support_legacy_strings():
    records = normalize_memory_records(
        [MEMORIES[0], "The candidate has practical experience with RAG."]
    )

    assert records[0]["id"] == "project_1"
    assert records[1]["id"] == "memory_2"


def test_claims_cannot_reference_unretrieved_memories():
    claims = [
        EvidenceBackedClaim(
            claim="I built an agentic workflow with LangGraph.",
            supporting_memory_ids=["missing_memory"],
        )
    ]

    with pytest.raises(ValueError, match="were not retrieved"):
        validate_claim_evidence(claims, MEMORIES)


def test_claims_cannot_strengthen_built_into_designed():
    claims = [
        EvidenceBackedClaim(
            claim="I designed an agentic workflow with LangGraph.",
            supporting_memory_ids=["project_1"],
        )
    ]

    with pytest.raises(ValueError, match="unsupported wording"):
        validate_claim_evidence(claims, MEMORIES)


def test_risky_wording_is_allowed_only_when_present_in_evidence():
    memories = [
        {
            "id": "project_2",
            "type": "project",
            "content": "The candidate designed an end-to-end retrieval pipeline.",
        }
    ]
    claims = [
        EvidenceBackedClaim(
            claim="I designed an end-to-end retrieval pipeline.",
            supporting_memory_ids=["project_2"],
        )
    ]

    validate_claim_evidence(claims, memories)


def test_claim_evidence_must_appear_in_email_body():
    draft = EmailDraft(
        subject="Application",
        body="I built an agentic workflow with LangGraph.",
        claim_evidence=[
            EvidenceBackedClaim(
                claim="I work with Python and FastAPI.",
                supporting_memory_ids=["skill_1"],
            )
        ],
    )

    with pytest.raises(ValueError, match="appear verbatim"):
        validate_grounded_email_draft(draft, MEMORIES)


def test_valid_grounded_email_passes():
    draft = EmailDraft(
        subject="Application",
        body=(
            "Dear Hiring Team,\n\n"
            "I built an agentic workflow with LangGraph. "
            "I work with Python and FastAPI.\n\n"
            "Kind regards"
        ),
        claim_evidence=[
            EvidenceBackedClaim(
                claim="I built an agentic workflow with LangGraph.",
                supporting_memory_ids=["project_1"],
            ),
            EvidenceBackedClaim(
                claim="I work with Python and FastAPI.",
                supporting_memory_ids=["skill_1"],
            ),
        ],
    )

    validate_grounded_email_draft(draft, MEMORIES)


def test_prompts_require_conservative_claim_evidence():
    assert "supporting memory IDs" in JOB_MATCH_SYSTEM_PROMPT
    assert "Every factual candidate claim" in EMAIL_DRAFT_SYSTEM_PROMPT
    assert "Do not transform an interest" in EMAIL_DRAFT_SYSTEM_PROMPT
    assert "LangChain" in EMAIL_DRAFT_SYSTEM_PROMPT
