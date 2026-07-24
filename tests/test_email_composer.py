import pytest
from pydantic import ValidationError

from app.email_composer import (
    compose_grounded_email_draft,
    deterministic_fallback_selection,
    memory_to_first_person_claim,
    validate_memory_selection,
)
from app.schemas import EmailEvidenceSelection, JobAnalysis, MatchInsight
from app.services.llm import generate_application_email_draft


MEMORIES = [
    {
        "id": "identity_1",
        "type": "identity",
        "content": "The demo candidate is an early-career machine learning engineer.",
    },
    {
        "id": "project_1",
        "type": "project",
        "content": "The demo candidate built an agentic workflow with LangGraph.",
    },
    {
        "id": "skill_1",
        "type": "skill",
        "content": "The demo candidate works with Python and FastAPI.",
    },
    {
        "id": "preference_1",
        "type": "preference",
        "content": "The demo candidate prefers concise application emails.",
    },
]


class FakeSelectionLLM:
    def __init__(self, responses):
        self.responses = list(responses)

    def invoke(self, _messages):
        return self.responses.pop(0)


def test_memory_to_first_person_claim_handles_common_candidate_grammar():
    assert memory_to_first_person_claim(MEMORIES[0]["content"]) == (
        "I am an early-career machine learning engineer."
    )
    assert memory_to_first_person_claim(MEMORIES[1]["content"]) == (
        "I built an agentic workflow with LangGraph."
    )
    assert memory_to_first_person_claim(MEMORIES[2]["content"]) == (
        "I work with Python and FastAPI."
    )
    assert memory_to_first_person_claim(MEMORIES[3]["content"]) == (
        "I prefer concise application emails."
    )


def test_email_selection_rejects_more_than_three_memories():
    with pytest.raises(ValidationError):
        EmailEvidenceSelection(
            selected_memory_ids=["a", "b", "c", "d"],
        )


def test_unknown_selected_memory_is_rejected():
    selection = EmailEvidenceSelection(selected_memory_ids=["missing"])

    with pytest.raises(ValueError, match="were not retrieved"):
        validate_memory_selection(selection, MEMORIES)


def test_composer_builds_body_only_from_selected_memory_evidence():
    selection = EmailEvidenceSelection(
        selected_memory_ids=["project_1", "skill_1"],
        tone="premium",
    )
    draft = compose_grounded_email_draft(
        job_analysis=JobAnalysis(
            company="Example AI",
            role="Junior LLM Engineer",
            domain_focus=["agentic AI"],
            tools_and_stack=["Python"],
        ),
        selection=selection,
        memory_records=MEMORIES,
    )

    assert draft.subject == "Application — Junior LLM Engineer"
    assert draft.tone == "premium"
    assert [item.supporting_memory_ids for item in draft.claim_evidence] == [
        ["project_1"],
        ["skill_1"],
    ]
    assert "I built an agentic workflow with LangGraph." in draft.body
    assert "I work with Python and FastAPI." in draft.body
    assert "early-career" not in draft.body
    assert "prompt engineering" not in draft.body
    assert "available to start" not in draft.body


def test_every_candidate_fact_in_deterministic_body_comes_from_ledger():
    selection = EmailEvidenceSelection(
        selected_memory_ids=["identity_1", "project_1", "skill_1"]
    )
    draft = compose_grounded_email_draft(
        job_analysis=JobAnalysis(company="Example AI", role="ML Engineer"),
        selection=selection,
        memory_records=MEMORIES,
    )

    evidence_paragraph = " ".join(item.claim for item in draft.claim_evidence)
    assert evidence_paragraph in draft.body
    assert len(draft.claim_evidence) == 3
    for item in draft.claim_evidence:
        assert item.claim in draft.body


def test_fallback_prioritizes_project_skill_and_avoids_preference():
    selection = deterministic_fallback_selection(MEMORIES, limit=3)

    assert selection.selected_memory_ids == ["project_1", "skill_1", "identity_1"]
    assert "preference_1" not in selection.selected_memory_ids


def test_service_uses_llm_only_to_select_memory_ids(monkeypatch):
    fake_llm = FakeSelectionLLM(
        [EmailEvidenceSelection(selected_memory_ids=["project_1", "skill_1"])]
    )
    monkeypatch.setattr(
        "app.services.llm.get_email_evidence_selection_llm",
        lambda: fake_llm,
    )

    draft = generate_application_email_draft(
        job_analysis=JobAnalysis(company="Example AI", role="LLM Engineer"),
        match_insight=MatchInsight(),
        retrieved_profile_memories=MEMORIES,
    )

    assert [item.supporting_memory_ids for item in draft.claim_evidence] == [
        ["project_1"],
        ["skill_1"],
    ]
    assert "I built an agentic workflow with LangGraph." in draft.body
    assert "I work with Python and FastAPI." in draft.body


def test_service_falls_back_safely_after_two_invalid_selections(monkeypatch):
    fake_llm = FakeSelectionLLM(
        [
            EmailEvidenceSelection(selected_memory_ids=["missing"]),
            EmailEvidenceSelection(selected_memory_ids=["still_missing"]),
        ]
    )
    monkeypatch.setattr(
        "app.services.llm.get_email_evidence_selection_llm",
        lambda: fake_llm,
    )

    draft = generate_application_email_draft(
        job_analysis=JobAnalysis(company="Example AI", role="ML Engineer"),
        match_insight=MatchInsight(),
        retrieved_profile_memories=MEMORIES,
    )

    assert [item.supporting_memory_ids[0] for item in draft.claim_evidence] == [
        "project_1",
        "skill_1",
        "identity_1",
    ]
    assert "preference_1" not in {
        item.supporting_memory_ids[0] for item in draft.claim_evidence
    }
