import pytest

from app.email_composer import (
    deterministic_fallback_selection,
    validate_memory_selection,
)
from app.relevance import rank_memory_records_for_job
from app.schemas import EmailEvidenceSelection, JobAnalysis


MEMORIES = [
    {
        "id": "identity_1",
        "type": "identity",
        "content": "The demo candidate is an early-career machine learning engineer.",
    },
    {
        "id": "experience_1",
        "type": "experience",
        "content": (
            "The demo candidate evaluated a machine learning matching system using ROC-AUC, "
            "threshold analysis and structured error reviews."
        ),
    },
    {
        "id": "project_1",
        "type": "project",
        "content": "The demo candidate built an agentic workflow with LangGraph.",
    },
    {
        "id": "project_2",
        "type": "project",
        "content": (
            "The demo candidate developed a retrieval prototype using sentence embeddings, "
            "FAISS and explicit relevance evaluation."
        ),
    },
    {
        "id": "project_3",
        "type": "project",
        "content": (
            "The demo candidate created a FastAPI model-serving service and containerized it "
            "with Docker."
        ),
    },
    {
        "id": "skill_2",
        "type": "skill",
        "content": "The demo candidate has practical experience with NLP, LLM APIs and RAG.",
    },
]


def test_rag_offer_ranks_retrieval_project_first():
    job = JobAnalysis(
        role="RAG Retrieval Engineer",
        required_skills=["sentence embeddings", "FAISS"],
        tools_and_stack=["FAISS"],
        domain_focus=["RAG", "semantic search"],
        missions_summary=["Evaluate retrieval relevance"],
    )

    ranked = rank_memory_records_for_job(job, MEMORIES)

    assert ranked[0]["id"] == "project_2"
    assert ranked[0]["relevance_score"] > ranked[-1]["relevance_score"]
    assert "FAISS" in ranked[0]["aligned_job_terms"]


def test_serving_offer_ranks_fastapi_docker_project_first():
    job = JobAnalysis(
        role="ML Platform Engineer",
        required_skills=["FastAPI", "Docker"],
        tools_and_stack=["FastAPI", "Docker"],
        domain_focus=["model serving", "MLOps"],
    )

    ranked = rank_memory_records_for_job(job, MEMORIES)

    assert ranked[0]["id"] == "project_3"
    assert {"FastAPI", "Docker"}.issubset(set(ranked[0]["aligned_job_terms"]))


def test_evaluation_offer_ranks_metrics_experience_first():
    job = JobAnalysis(
        role="Machine Learning Evaluation Engineer",
        required_skills=["ROC-AUC", "threshold analysis"],
        missions_summary=["Perform structured error reviews"],
    )

    ranked = rank_memory_records_for_job(job, MEMORIES)

    assert ranked[0]["id"] == "experience_1"
    assert ranked[0]["relevance_score"] > 0


def test_selection_rejects_generic_memory_when_aligned_evidence_exists():
    job = JobAnalysis(
        role="RAG Engineer",
        required_skills=["FAISS", "RAG"],
        tools_and_stack=["FAISS"],
    )
    ranked = rank_memory_records_for_job(job, MEMORIES)
    selection = EmailEvidenceSelection(selected_memory_ids=["identity_1"])

    with pytest.raises(ValueError, match="ignored all memories"):
        validate_memory_selection(selection, ranked)


def test_fallback_uses_relevance_and_evidence_type_diversity():
    job = JobAnalysis(
        role="RAG Engineer",
        required_skills=["FAISS", "RAG", "NLP"],
        tools_and_stack=["FAISS"],
        domain_focus=["retrieval"],
    )

    selection = deterministic_fallback_selection(
        MEMORIES,
        job_analysis=job,
        limit=3,
    )

    assert selection.selected_memory_ids[0] == "project_2"
    assert "skill_2" in selection.selected_memory_ids
    assert "identity_1" not in selection.selected_memory_ids
