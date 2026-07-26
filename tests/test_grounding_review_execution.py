import json
from types import SimpleNamespace

import scripts.prepare_email_grounding_review as review_script


def test_isolated_grounding_uses_expected_analysis_without_product_graph(monkeypatch):
    case = {
        "id": "cv_001",
        "job_text": "This text must not be sent to an LLM in isolated mode.",
        "expected": {
            "company": "Vision Lab",
            "role": "Computer Vision Engineer",
            "location": "Paris",
            "contract_type": "Full-time",
            "start_date": "Unknown",
            "missions_summary": ["Train computer vision models"],
            "required_skills": ["Python", "PyTorch"],
            "preferred_skills": [],
            "tools_and_stack": ["Python", "PyTorch"],
            "profile_summary": "Machine learning engineer",
            "domain_focus": ["computer vision"],
            "key_highlights_for_candidate": [],
        },
    }
    documents = [
        SimpleNamespace(
            page_content="The demo candidate works with Python.",
            metadata={"id": "skill_python", "type": "skill", "topic": "python"},
        ),
        SimpleNamespace(
            page_content="The demo candidate works with PyTorch.",
            metadata={"id": "skill_pytorch", "type": "skill", "topic": "pytorch"},
        ),
        SimpleNamespace(
            page_content="The demo candidate works with SQL.",
            metadata={"id": "skill_sql", "type": "skill", "topic": "sql"},
        ),
    ]
    monkeypatch.setattr(
        review_script,
        "retrieve_profile_context",
        lambda query, k: documents,
    )
    monkeypatch.setattr(
        review_script.jobcopilot_graph,
        "invoke",
        lambda _state: (_ for _ in ()).throw(
            AssertionError("The product graph must not run in isolated mode.")
        ),
    )

    result = review_script.run_isolated_grounding_case(case)
    selected_ids = [
        item["supporting_memory_ids"][0]
        for item in result["email_draft"]["claim_evidence"]
    ]

    assert selected_ids == ["skill_python", "skill_pytorch"]
    assert "SQL" not in result["email_draft"]["body"]
    assert result["job_analysis"]["company"] == "Vision Lab"


def test_partial_failure_preserves_completed_records_and_manifest(tmp_path):
    cases = [
        {"id": "offer_001", "category": "LLM", "language": "en"},
        {"id": "offer_002", "category": "ML", "language": "en"},
    ]
    calls = {"count": 0}

    def runner(_case):
        calls["count"] += 1
        if calls["count"] == 2:
            raise RuntimeError("provider credits exhausted")
        return {
            "retrieved_memory_records": [
                {
                    "id": "skill_python",
                    "type": "skill",
                    "content": "The demo candidate works with Python.",
                }
            ],
            "email_draft": {
                "subject": "Application — Engineer",
                "body": "I work with Python.",
                "composition_variant": "direct",
                "claim_evidence": [
                    {
                        "claim": "I work with Python.",
                        "supporting_memory_ids": ["skill_python"],
                        "relevance_score": 5.0,
                        "aligned_job_terms": ["Python"],
                    }
                ],
            },
        }

    output = tmp_path / "review.jsonl"
    errors = tmp_path / "errors.jsonl"
    manifest = tmp_path / "manifest.json"

    records, failures = review_script.prepare_records(
        cases=cases,
        runner=runner,
        output=output,
        errors_output=errors,
        manifest_output=manifest,
        sampling="head",
        memory_profile=tmp_path / "memories.json",
        execution_mode="end-to-end",
        memory_by_content={},
    )

    assert len(records) == 1
    assert len(failures) == 1
    assert len(output.read_text(encoding="utf-8").splitlines()) == 1
    error_record = json.loads(errors.read_text(encoding="utf-8").strip())
    manifest_record = json.loads(manifest.read_text(encoding="utf-8"))
    assert error_record["job_id"] == "offer_002"
    assert manifest_record["status"] == "partial"
    assert manifest_record["completed_jobs"] == 1
    assert manifest_record["failed_job_id"] == "offer_002"
