from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass
from time import perf_counter
from typing import Any, Iterator

from langchain_core.runnables import Runnable, RunnableConfig


@dataclass(frozen=True)
class LLMCallEvent:
    """Privacy-safe metadata for one provider attempt.

    Prompts, outputs, API keys and raw provider errors are deliberately excluded.
    """

    provider: str
    model: str
    operation: str
    status: str
    duration_ms: int
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    error_type: str | None = None

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


_TRACE_EVENTS: ContextVar[list[LLMCallEvent] | None] = ContextVar(
    "jobcopilot_llm_trace_events",
    default=None,
)


@contextmanager
def capture_llm_telemetry() -> Iterator[list[LLMCallEvent]]:
    """Capture provider attempts made in the current execution context."""

    events: list[LLMCallEvent] = []
    token = _TRACE_EVENTS.set(events)
    try:
        yield events
    finally:
        _TRACE_EVENTS.reset(token)


def _extract_usage(result: Any) -> tuple[int | None, int | None, int | None]:
    usage = getattr(result, "usage_metadata", None)
    if not isinstance(usage, dict):
        return None, None, None

    input_tokens = usage.get("input_tokens")
    output_tokens = usage.get("output_tokens")
    total_tokens = usage.get("total_tokens")
    if total_tokens is None and isinstance(input_tokens, int) and isinstance(output_tokens, int):
        total_tokens = input_tokens + output_tokens
    return input_tokens, output_tokens, total_tokens


def _append_event(event: LLMCallEvent) -> None:
    sink = _TRACE_EVENTS.get()
    if sink is not None:
        sink.append(event)


class TelemetryRunnable(Runnable[Any, Any]):
    """Runnable wrapper that records the provider actually attempted and used."""

    def __init__(
        self,
        runnable: Runnable[Any, Any],
        *,
        provider: str,
        model: str,
        operation: str,
    ) -> None:
        self._runnable = runnable
        self.provider = provider
        self.model = model
        self.operation = operation

    def invoke(
        self,
        input: Any,
        config: RunnableConfig | None = None,
        **kwargs: Any,
    ) -> Any:
        started = perf_counter()
        try:
            result = self._runnable.invoke(input, config=config, **kwargs)
        except Exception as exc:
            _append_event(
                LLMCallEvent(
                    provider=self.provider,
                    model=self.model,
                    operation=self.operation,
                    status="error",
                    duration_ms=round((perf_counter() - started) * 1000),
                    error_type=type(exc).__name__,
                )
            )
            raise

        input_tokens, output_tokens, total_tokens = _extract_usage(result)
        _append_event(
            LLMCallEvent(
                provider=self.provider,
                model=self.model,
                operation=self.operation,
                status="success",
                duration_ms=round((perf_counter() - started) * 1000),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
            )
        )
        return result


def instrument_llm_runnable(
    runnable: Runnable[Any, Any],
    *,
    provider: str,
    model: str,
    operation: str,
) -> TelemetryRunnable:
    return TelemetryRunnable(
        runnable,
        provider=provider,
        model=model,
        operation=operation,
    )


def serialize_llm_events(events: list[LLMCallEvent]) -> list[dict[str, Any]]:
    return [event.model_dump() for event in events]


def _sum_optional_ints(events: list[dict[str, Any]], field: str) -> int | None:
    values = [
        event.get(field)
        for event in events
        if isinstance(event.get(field), int)
    ]
    return sum(values) if values else None


def _nearest_rank_percentile(values: list[int], percentile: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round(percentile * (len(ordered) - 1))))
    return ordered[index]


def summarize_llm_events(events: list[LLMCallEvent] | list[dict[str, Any]]) -> dict[str, Any]:
    normalized = [
        event.model_dump() if isinstance(event, LLMCallEvent) else dict(event)
        for event in events
    ]
    successes = [event for event in normalized if event.get("status") == "success"]
    failures = [event for event in normalized if event.get("status") == "error"]
    providers_used = list(
        dict.fromkeys(str(event.get("provider", "unknown")) for event in successes)
    )
    models_used = list(
        dict.fromkeys(str(event.get("model", "unknown")) for event in successes)
    )
    final_success = successes[-1] if successes else None
    success_durations = [
        int(event.get("duration_ms", 0) or 0)
        for event in successes
    ]
    total_duration_ms = sum(
        int(event.get("duration_ms", 0) or 0)
        for event in normalized
    )

    operation_breakdown: dict[str, dict[str, Any]] = {}
    for event in normalized:
        operation = str(event.get("operation", "unknown"))
        bucket = operation_breakdown.setdefault(
            operation,
            {
                "attempts": 0,
                "successful_calls": 0,
                "failed_attempts": 0,
                "duration_ms": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "token_usage_available": False,
            },
        )
        bucket["attempts"] += 1
        bucket["duration_ms"] += int(event.get("duration_ms", 0) or 0)
        if event.get("status") == "success":
            bucket["successful_calls"] += 1
        elif event.get("status") == "error":
            bucket["failed_attempts"] += 1
        for field in ("input_tokens", "output_tokens", "total_tokens"):
            value = event.get(field)
            if isinstance(value, int):
                bucket[field] += value
                bucket["token_usage_available"] = True

    attempts = len(normalized)
    successful_calls = len(successes)
    failed_attempts = len(failures)
    return {
        "attempts": attempts,
        "successful_calls": successful_calls,
        "failed_attempts": failed_attempts,
        "success_rate": successful_calls / attempts if attempts else 1.0,
        "error_rate": failed_attempts / attempts if attempts else 0.0,
        "providers_used": providers_used,
        "models_used": models_used,
        "final_provider": final_success.get("provider") if final_success else None,
        "final_model": final_success.get("model") if final_success else None,
        "fallback_used": bool(failures and successes),
        "total_duration_ms": total_duration_ms,
        "mean_success_latency_ms": (
            sum(success_durations) / len(success_durations)
            if success_durations
            else None
        ),
        "p95_success_latency_ms": _nearest_rank_percentile(success_durations, 0.95),
        "input_tokens": _sum_optional_ints(successes, "input_tokens"),
        "output_tokens": _sum_optional_ints(successes, "output_tokens"),
        "total_tokens": _sum_optional_ints(successes, "total_tokens"),
        "operation_breakdown": operation_breakdown,
    }
