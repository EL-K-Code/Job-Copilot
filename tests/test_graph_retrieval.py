from types import SimpleNamespace

from app.graph import analyze_job_node, retrieve_memory_node
from app.schemas import JobAnalysis


def test_retrieval_query_includes_missions_and_preferred_skills(monkeypatch):
    analysis = JobAnalysis(
        company="Example AI",
        role="Computer Vision Engineer",
        missions_summary=["Train image classifiers", "Evaluate model robustness"],
        required_skills=["Python", "PyTorch"],
        preferred_skills=["OpenCV"],
        tools_and_stack=["Docker"],
        domain_focus=["computer vision"],
    )
    monkeypatch.setattr("app.graph.analyze_job_offer", lambda _text: analysis)

    result = analyze_job_node({"job_text": "synthetic offer"})
    query = result["retrieval_query"]

    assert "Missions: Train image classifiers, Evaluate model robustness" in query
    assert "Preferred skills: OpenCV" in query
    assert "Required skills: Python, PyTorch" in query
    assert "Domain focus: computer vision" in query


def test_retrieve_memory_node_requests_broader_candidate_pool(monkeypatch):
    captured = {}

    def fake_retrieve(query, k):
        captured["query"] = query
        captured["k"] = k
        return [
            SimpleNamespace(
                page_content="The candidate works with Python.",
                metadata={"id": "skill_1", "type": "skill"},
            )
        ]

    monkeypatch.setattr("app.graph.retrieve_profile_context", fake_retrieve)

    result = retrieve_memory_node({"retrieval_query": "computer vision Python"})

    assert captured == {"query": "computer vision Python", "k": 8}
    assert result["retrieved_memory_records"] == [
        {
            "id": "skill_1",
            "type": "skill",
            "content": "The candidate works with Python.",
        }
    ]
