from __future__ import annotations

import json

from app.services.evaluation_observability import (
    load_published_retrieval_summary,
    summarize_application_observability,
    summarize_grounding_integrity,
    summarize_retrieval_trace,
)


def test_grounding_integrity_distinguishes_supported_and_unknown_evidence():
    summary = summarize_grounding_integrity(
        job_analysis={
            "required_skills": ["Python", "Docker"],
            "preferred_skills": [],
            "tools_and_stack": ["Python"],
            "domain_focus": ["Machine Learning"],
        },
        email_draft={
            "claim_evidence": [
                {
                    "claim": "I use Python.",
                    "supporting_memory_ids": ["m1"],
                    "aligned_job_terms": ["Python"],
                },
                {
                    "claim": "I use Kubernetes.",
                    "supporting_memory_ids": ["missing"],
                    "aligned_job_terms": ["Docker"],
                },
            ]
        },
        application_pack={"missing_job_terms": ["Machine Learning"]},
        memory_records=[{"id": "m1", "content": "Uses Python."}],
    )

    assert summary["claim_count"] == 2
    assert summary["grounded_claims"] == 1
    assert summary["unsupported_claims"] == 1
    assert summary["unknown_memory_ids"] == ["missing"]
    assert summary["evidence_coverage"] == 0.5
    assert summary["grounding_integrity_pass"] is False
    assert summary["explicit_job_term_count"] == 3
    assert summary["covered_job_term_count"] == 2
    assert summary["job_term_evidence_coverage"] == 2 / 3
    assert summary["missing_job_term_count"] == 1


def test_retrieval_trace_reports_dense_sparse_and_reranker_provenance():
    records = [
        {
            "id": "m1",
            "retrieval_strategy": "hybrid_rrf_cross_encoder",
            "retrieval_final_rank": 1,
            "retrieval_dense_rank": 2,
            "retrieval_sparse_rank": 1,
            "retrieval_fusion_rank": 1,
            "retrieval_reranker_applied": True,
        },
        {
            "id": "m2",
            "retrieval_strategy": "hybrid_rrf_cross_encoder",
            "retrieval_final_rank": 2,
            "retrieval_sparse_rank": 2,
            "retrieval_fusion_rank": 3,
            "retrieval_reranker_applied": True,
        },
        {
            "id": "m3",
            "retrieval_strategy": "hybrid_rrf_cross_encoder",
            "retrieval_final_rank": 3,
            "retrieval_dense_rank": 1,
            "retrieval_fusion_rank": 2,
            "retrieval_reranker_applied": True,
        },
    ]

    summary = summarize_retrieval_trace(records)

    assert summary["evidence_count"] == 3
    assert summary["strategy"] == "hybrid_rrf_cross_encoder"
    assert summary["reranker_applied"] is True
    assert summary["reranked_evidence_count"] == 3
    assert summary["dense_and_sparse_count"] == 1
    assert summary["sparse_only_count"] == 1
    assert summary["dense_only_count"] == 1
    assert summary["mean_final_rank"] == 2


def test_application_observability_includes_privacy_safe_llm_runtime_metrics():
    results = {
        "job_analysis": {
            "required_skills": ["Python"],
            "preferred_skills": [],
            "tools_and_stack": [],
            "domain_focus": [],
        },
        "email_draft": {
            "claim_evidence": [
                {
                    "claim": "I use Python.",
                    "supporting_memory_ids": ["m1"],
                    "aligned_job_terms": ["Python"],
                }
            ]
        },
        "application_pack": {"missing_job_terms": []},
        "retrieved_memory_records": [
            {
                "id": "m1",
                "content": "Uses Python.",
                "retrieval_strategy": "hybrid_rrf",
                "retrieval_final_rank": 1,
                "retrieval_dense_rank": 1,
                "retrieval_sparse_rank": 1,
                "retrieval_fusion_rank": 1,
                "retrieval_reranker_applied": False,
            }
        ],
        "llm_telemetry": [
            {
                "provider": "openai",
                "model": "gpt-test",
                "operation": "JobAnalysis",
                "status": "success",
                "duration_ms": 120,
                "input_tokens": 100,
                "output_tokens": 20,
                "total_tokens": 120,
                "error_type": None,
            },
            {
                "provider": "openai",
                "model": "gpt-test",
                "operation": "MatchInsight",
                "status": "success",
                "duration_ms": 180,
                "input_tokens": 80,
                "output_tokens": 30,
                "total_tokens": 110,
                "error_type": None,
            },
        ],
    }

    summary = summarize_application_observability(results)

    assert summary["grounding"]["grounding_integrity_pass"] is True
    assert summary["retrieval"]["strategy"] == "hybrid_rrf"
    assert summary["llm"]["successful_calls"] == 2
    assert summary["llm"]["success_rate"] == 1.0
    assert summary["llm"]["total_duration_ms"] == 300
    assert summary["llm"]["input_tokens"] == 180
    assert summary["llm"]["output_tokens"] == 50
    assert summary["llm"]["total_tokens"] == 230
    assert summary["llm"]["p95_success_latency_ms"] == 180
    assert "prompt" not in json.dumps(summary).lower()


def test_published_retrieval_summary_loader_is_optional_and_validated(tmp_path):
    missing = tmp_path / "missing.json"
    assert load_published_retrieval_summary(missing) is None

    report = tmp_path / "summary.json"
    report.write_text('{"number_of_cases": 20, "strategies": {}}', encoding="utf-8")
    assert load_published_retrieval_summary(report)["number_of_cases"] == 20

    invalid = tmp_path / "invalid.json"
    invalid.write_text("[]", encoding="utf-8")
    try:
        load_published_retrieval_summary(invalid)
    except ValueError as exc:
        assert "JSON object" in str(exc)
    else:
        raise AssertionError("Expected a ValueError for a non-object published summary")
