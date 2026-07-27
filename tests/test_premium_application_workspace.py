from pathlib import Path

from app.ui.application_workspace import (
    JOB_PLACEHOLDER,
    evidence_records_for_claim,
    normalize_initial_job_text,
    telemetry_badges,
)


def test_legacy_job_placeholder_becomes_empty_input():
    assert normalize_initial_job_text(JOB_PLACEHOLDER) == ""
    assert normalize_initial_job_text(f"  {JOB_PLACEHOLDER}  ") == ""
    assert normalize_initial_job_text("Real job offer") == "Real job offer"


def test_evidence_records_are_limited_to_explicit_supporting_ids():
    memories = [
        {"id": "m1", "content": "Uses Python."},
        {"id": "m2", "content": "Uses SQL."},
        {"id": "m3", "content": "Uses Docker."},
    ]
    claim = {"supporting_memory_ids": ["m2", "missing", "m1"]}

    selected = evidence_records_for_claim(claim, memories)

    assert [item["id"] for item in selected] == ["m2", "m1"]


def test_telemetry_badges_report_actual_provider_and_grounding_count():
    events = [
        {
            "provider": "openai",
            "model": "gpt-4.1-mini",
            "operation": "JobAnalysis",
            "status": "success",
            "duration_ms": 250,
        }
    ]

    badges = telemetry_badges(events, 2)

    assert badges["provider"] == "Openai"
    assert badges["model"] == "gpt-4.1-mini"
    assert badges["grounding_label"] == "2 grounded claims"
    assert badges["fallback_used"] is False


def test_project_streamlit_configuration_keeps_cv_limit_and_minimal_toolbar():
    config = Path(".streamlit/config.toml").read_text(encoding="utf-8")

    assert 'toolbarMode = "minimal"' in config
    assert "maxUploadSize = 10" in config
    assert 'showErrorDetails = "none"' in config
    assert "gatherUsageStats = false" in config
