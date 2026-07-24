import pytest

from app.grounding_review import (
    flatten_review_claims,
    summarize_grounding_reviews,
)


def _review_records():
    return [
        {
            "job_id": "job-1",
            "retrieved_memories": [
                {"id": "project_1", "content": "Built a LangGraph workflow."},
                {"id": "skill_2", "content": "Worked with RAG."},
            ],
            "claims": [
                {
                    "claim": "The candidate built a LangGraph workflow.",
                    "label": "supported",
                    "supporting_memory_ids": ["project_1"],
                },
                {
                    "claim": "The candidate deployed Kubernetes in production.",
                    "label": "unsupported",
                    "supporting_memory_ids": [],
                },
                {
                    "claim": "The candidate has broad production ownership.",
                    "label": "ambiguous",
                    "supporting_memory_ids": ["skill_2"],
                },
            ],
        }
    ]


def test_grounding_review_summary_reports_unsupported_claim_rate():
    result = summarize_grounding_reviews(_review_records())

    assert result["number_of_reviewed_jobs"] == 1
    assert result["number_of_claims"] == 3
    assert result["supported_rate"] == 1 / 3
    assert result["unsupported_claim_rate"] == 1 / 3
    assert result["ambiguous_rate"] == 1 / 3
    assert result["by_job"]["job-1"]["unsupported_claim_rate"] == 1 / 3


def test_supported_claim_requires_retrieved_evidence():
    records = _review_records()
    records[0]["claims"][0]["supporting_memory_ids"] = []

    with pytest.raises(ValueError, match="require at least one supporting memory"):
        flatten_review_claims(records)


def test_review_rejects_evidence_not_present_in_retrieval():
    records = _review_records()
    records[0]["claims"][0]["supporting_memory_ids"] = ["unknown_memory"]

    with pytest.raises(ValueError, match="were not retrieved"):
        flatten_review_claims(records)


def test_unsupported_claim_cannot_list_supporting_evidence():
    records = _review_records()
    records[0]["claims"][1]["supporting_memory_ids"] = ["project_1"]

    with pytest.raises(ValueError, match="must not list supporting memories"):
        flatten_review_claims(records)
