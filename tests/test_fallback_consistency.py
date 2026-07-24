from app.email_composer import (
    deterministic_fallback_selection,
    validate_memory_selection,
)


def test_fallback_uses_all_aligned_memories_before_type_diversity():
    ranked_records = [
        {
            "id": "project_1",
            "type": "project",
            "content": "The candidate built a RAG prototype.",
            "relevance_score": 12.0,
        },
        {
            "id": "project_2",
            "type": "project",
            "content": "The candidate evaluated a retrieval pipeline.",
            "relevance_score": 9.0,
        },
        {
            "id": "project_3",
            "type": "project",
            "content": "The candidate implemented a FAISS search experiment.",
            "relevance_score": 7.0,
        },
        {
            "id": "identity_1",
            "type": "identity",
            "content": "The candidate is an early-career engineer.",
            "relevance_score": 0.0,
        },
    ]

    selection = deterministic_fallback_selection(ranked_records, limit=3)

    assert selection.selected_memory_ids == ["project_1", "project_2", "project_3"]
    validate_memory_selection(selection, ranked_records)


def test_fallback_returns_shorter_selection_when_aligned_evidence_is_limited():
    ranked_records = [
        {
            "id": "project_1",
            "type": "project",
            "content": "The candidate built a RAG prototype.",
            "relevance_score": 10.0,
        },
        {
            "id": "skill_1",
            "type": "skill",
            "content": "The candidate works with Python.",
            "relevance_score": 5.0,
        },
        {
            "id": "identity_1",
            "type": "identity",
            "content": "The candidate is an early-career engineer.",
            "relevance_score": 0.0,
        },
    ]

    selection = deterministic_fallback_selection(ranked_records, limit=3)

    assert selection.selected_memory_ids == ["project_1", "skill_1"]
    validate_memory_selection(selection, ranked_records)
