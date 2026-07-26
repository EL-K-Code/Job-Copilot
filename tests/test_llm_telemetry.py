from __future__ import annotations

from langchain_core.runnables import RunnableLambda

from app.services.llm_telemetry import (
    capture_llm_telemetry,
    instrument_llm_runnable,
    serialize_llm_events,
    summarize_llm_events,
)
from app.services.model_provider import _with_fallbacks


def test_successful_provider_attempt_is_attributed_without_payload_logging():
    runnable = instrument_llm_runnable(
        RunnableLambda(lambda value: f"result:{value}"),
        provider="openai",
        model="gpt-test",
        operation="JobAnalysis",
    )

    with capture_llm_telemetry() as events:
        assert runnable.invoke("private prompt") == "result:private prompt"

    serialized = serialize_llm_events(events)
    assert serialized == [
        {
            "provider": "openai",
            "model": "gpt-test",
            "operation": "JobAnalysis",
            "status": "success",
            "duration_ms": serialized[0]["duration_ms"],
            "input_tokens": None,
            "output_tokens": None,
            "total_tokens": None,
            "error_type": None,
        }
    ]
    assert "private prompt" not in str(serialized)


def test_fallback_trace_records_failed_primary_and_successful_secondary():
    primary = instrument_llm_runnable(
        RunnableLambda(
            lambda _value: (_ for _ in ()).throw(RuntimeError("secret provider error"))
        ),
        provider="openai",
        model="gpt-test",
        operation="MatchInsight",
    )
    secondary = instrument_llm_runnable(
        RunnableLambda(lambda value: f"anthropic:{value}"),
        provider="anthropic",
        model="claude-test",
        operation="MatchInsight",
    )
    runnable = _with_fallbacks([primary, secondary])

    with capture_llm_telemetry() as events:
        assert runnable.invoke("job") == "anthropic:job"

    serialized = serialize_llm_events(events)
    assert [event["provider"] for event in serialized] == ["openai", "anthropic"]
    assert [event["status"] for event in serialized] == ["error", "success"]
    assert serialized[0]["error_type"] == "RuntimeError"
    assert "secret provider error" not in str(serialized)

    summary = summarize_llm_events(serialized)
    assert summary["final_provider"] == "anthropic"
    assert summary["fallback_used"] is True
    assert summary["failed_attempts"] == 1
    assert summary["successful_calls"] == 1


def test_nested_capture_contexts_do_not_leak_events():
    runnable = instrument_llm_runnable(
        RunnableLambda(lambda value: value),
        provider="openai",
        model="gpt-test",
        operation="AgentChat",
    )

    with capture_llm_telemetry() as outer:
        runnable.invoke("outer-1")
        with capture_llm_telemetry() as inner:
            runnable.invoke("inner")
        runnable.invoke("outer-2")

    assert len(outer) == 2
    assert len(inner) == 1
