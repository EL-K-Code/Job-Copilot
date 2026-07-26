import json
from pathlib import Path

from app.email_composer import deterministic_fallback_selection
from app.memory import load_profile_memories, profile_memories_to_documents
from app.relevance import rank_memory_records_for_job
from app.schemas import JobAnalysis


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ATOMIC_PROFILE = PROJECT_ROOT / "data" / "profile_memories.atomic.json"


def test_atomic_profile_has_unique_valid_records():
    memories = load_profile_memories(ATOMIC_PROFILE)

    assert len(memories) >= 25
    assert len({memory["id"] for memory in memories}) == len(memories)
    assert all(memory.get("topic") for memory in memories)
    assert all(memory.get("group_id") for memory in memories)


def test_atomic_skill_memories_do_not_bundle_unrelated_technologies():
    memories = load_profile_memories(ATOMIC_PROFILE)
    skill_memories = [memory for memory in memories if memory["type"] == "skill"]

    assert skill_memories
    for memory in skill_memories:
        content = memory["content"]
        assert "," not in content
        assert " and " not in content.casefold()


def test_document_conversion_preserves_atomic_audit_metadata():
    memories = load_profile_memories(ATOMIC_PROFILE)
    documents = profile_memories_to_documents(memories[:1])

    assert len(documents) == 1
    assert documents[0].metadata["id"] == memories[0]["id"]
    assert documents[0].metadata["topic"] == memories[0]["topic"]
    assert documents[0].metadata["group_id"] == memories[0]["group_id"]


def test_computer_vision_fallback_selects_only_python_and_pytorch_evidence():
    memories = json.loads(ATOMIC_PROFILE.read_text(encoding="utf-8"))
    job = JobAnalysis(
        company="Vision Lab",
        role="Computer Vision Engineer",
        required_skills=["Python", "PyTorch"],
        tools_and_stack=["Python", "PyTorch"],
        domain_focus=["computer vision"],
    )

    ranked = rank_memory_records_for_job(job, memories)
    selection = deterministic_fallback_selection(ranked, limit=3)

    assert set(selection.selected_memory_ids) == {"skill_python", "skill_pytorch"}
    selected_contents = {
        memory["content"]
        for memory in memories
        if memory["id"] in selection.selected_memory_ids
    }
    assert selected_contents == {
        "The demo candidate works with Python.",
        "The demo candidate works with PyTorch.",
    }


def test_data_pipeline_evidence_no_longer_carries_nlp_or_rag_claims():
    memories = json.loads(ATOMIC_PROFILE.read_text(encoding="utf-8"))
    pipeline_memory = next(
        memory for memory in memories if memory["id"] == "skill_data_pipelines"
    )

    normalized = pipeline_memory["content"].casefold()
    assert "data pipelines" in normalized
    assert "natural language processing" not in normalized
    assert "retrieval-augmented generation" not in normalized
    assert "large language model" not in normalized
