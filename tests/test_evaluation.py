import pytest

from app.evaluation import (
    evaluate_job_analysis,
    evaluate_retrieval_ranking,
    ndcg_at_k,
    reciprocal_rank,
    recall_at_k,
    set_precision_recall_f1,
    summarize_grounding_annotations,
)


def test_set_metrics_are_case_and_whitespace_insensitive():
    metrics = set_precision_recall_f1(
        predicted=[" Python ", "RAG"],
        expected=["python", "rag", "Docker"],
    )

    assert metrics["precision"] == 1.0
    assert metrics["recall"] == 2 / 3
    assert metrics["f1"] == 0.8


def test_job_analysis_evaluation_combines_scalar_and_list_scores():
    result = evaluate_job_analysis(
        predicted={
            "company": "Example Labs",
            "role": "ML Engineer",
            "required_skills": ["Python", "SQL"],
            "tools_and_stack": ["Docker"],
        },
        expected={
            "company": "example labs",
            "role": "ML Engineer",
            "required_skills": ["Python", "SQL"],
            "tools_and_stack": ["Docker", "Kubernetes"],
        },
    )

    assert result["scalar_accuracy"] == 1.0
    assert result["list_fields"]["required_skills"]["f1"] == 1.0
    assert result["list_fields"]["tools_and_stack"]["recall"] == 0.5


def test_retrieval_metrics_reward_early_relevant_results():
    retrieved = ["noise", "project_1", "skill_2"]
    relevant = ["project_1", "skill_2"]

    assert recall_at_k(retrieved, relevant, 1) == 0.0
    assert recall_at_k(retrieved, relevant, 3) == 1.0
    assert reciprocal_rank(retrieved, relevant) == 0.5
    assert ndcg_at_k(
        retrieved,
        {"project_1": 3, "skill_2": 2},
        3,
    ) < 1.0

    result = evaluate_retrieval_ranking(
        retrieved,
        relevant,
        {"project_1": 3, "skill_2": 2},
    )
    assert result["recall_at_3"] == 1.0
    assert result["reciprocal_rank"] == 0.5


def test_grounding_summary_reports_unsupported_claim_rate():
    result = summarize_grounding_annotations(
        [
            {"label": "supported"},
            {"label": "supported"},
            {"label": "unsupported"},
            {"label": "ambiguous"},
        ]
    )

    assert result["number_of_claims"] == 4
    assert result["supported_rate"] == 0.5
    assert result["unsupported_claim_rate"] == 0.25
    assert result["ambiguous_rate"] == 0.25


def test_grounding_summary_rejects_unknown_labels():
    with pytest.raises(ValueError, match="Invalid grounding label"):
        summarize_grounding_annotations([{"label": "mostly supported"}])
