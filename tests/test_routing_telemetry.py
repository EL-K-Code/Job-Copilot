from __future__ import annotations

from langchain_core.runnables import RunnableLambda

from app.services.llm_telemetry import (
    capture_llm_telemetry,
    instrument_llm_runnable,
    serialize_llm_events,
    summarize_llm_events,
)


def test_routed_call_records_tier_reason_without_prompt_payload():
    runnable = instrument_llm_runnable(
        RunnableLambda(lambda value: f"ok:{value}"),
        provider="openai",
        model="gpt-economy",
        operation="JobAnalysis",
        routing_tier="economy",
        routing_reason="operation_policy:JobAnalysis",
        routing_escalated=False,
    )

    with capture_llm_telemetry() as events:
        runnable.invoke("private job text")

    serialized = serialize_llm_events(events)
    assert serialized[0]["routing_tier"] == "economy"
    assert serialized[0]["routing_reason"] == "operation_policy:JobAnalysis"
    assert serialized[0]["routing_escalated"] is False
    assert "private job text" not in str(serialized)


def test_summary_counts_strong_tier_quality_escalation():
    events = [
        {
            "provider": "openai",
            "model": "gpt-standard",
            "operation": "MatchInsight",
            "status": "success",
            "duration_ms": 100,
            "routing_tier": "standard",
            "routing_reason": "operation_policy:MatchInsight",
            "routing_escalated": False,
        },
        {
            "provider": "openai",
            "model": "gpt-strong",
            "operation": "MatchInsightRepair",
            "status": "success",
            "duration_ms": 120,
            "routing_tier": "strong",
            "routing_reason": "claim_evidence_validation_failed",
            "routing_escalated": True,
        },
    ]
    summary = summarize_llm_events(events)
    assert summary["route_tiers"] == ["standard", "strong"]
    assert summary["escalation_attempts"] == 1
    assert summary["escalation_rate"] == 0.5
    assert summary["final_routing_tier"] == "strong"


def test_same_provider_model_recovery_is_not_reported_as_provider_fallback():
    events = [
        {
            "provider": "openai",
            "model": "gpt-economy",
            "operation": "JobAnalysis",
            "status": "error",
            "duration_ms": 25,
            "routing_tier": "economy",
        },
        {
            "provider": "openai",
            "model": "gpt-standard",
            "operation": "JobAnalysis",
            "status": "success",
            "duration_ms": 60,
            "routing_tier": "standard",
        },
    ]
    summary = summarize_llm_events(events)
    assert summary["fallback_used"] is False
    assert summary["provider_fallback_used"] is False
    assert summary["model_fallback_used"] is True
    assert summary["recovery_after_error"] is True
