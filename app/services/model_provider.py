from __future__ import annotations

from collections.abc import Sequence
import logging
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI

from app.config import settings
from app.services.llm_telemetry import instrument_llm_runnable

SUPPORTED_LLM_PROVIDERS = {"anthropic", "openai"}
_PROFILE_EXTRACTION_OPERATION = "ProfileExtraction"
logger = logging.getLogger(__name__)


def normalize_provider_name(value: str) -> str:
    provider = value.strip().lower()
    if provider not in SUPPORTED_LLM_PROVIDERS:
        supported = ", ".join(sorted(SUPPORTED_LLM_PROVIDERS))
        raise ValueError(
            f"Unsupported LLM provider '{value}'. Expected one of: {supported}."
        )
    return provider


def configured_provider_chain() -> tuple[str, ...]:
    """Return the primary provider followed by one optional distinct fallback."""
    primary = normalize_provider_name(settings.llm_provider)
    fallback_raw = settings.llm_fallback_provider.strip()
    if not fallback_raw:
        return (primary,)

    fallback = normalize_provider_name(fallback_raw)
    if fallback == primary:
        return (primary,)
    return (primary, fallback)


def provider_has_api_key(provider: str) -> bool:
    normalized = normalize_provider_name(provider)
    if normalized == "openai":
        return bool(settings.openai_api_key.strip())
    return bool(settings.anthropic_api_key.strip())


def active_provider_chain() -> tuple[str, ...]:
    """
    Return the configured chain while allowing an unavailable optional fallback.

    A missing primary key is always an error. A missing fallback key disables only that
    fallback, which keeps local and GitHub deployments usable with one provider.
    """
    configured = configured_provider_chain()
    primary, *fallbacks = configured
    if not provider_has_api_key(primary):
        if primary == "openai":
            settings.require_openai_api_key()
        settings.require_anthropic_api_key()

    active = [primary]
    for fallback in fallbacks:
        if provider_has_api_key(fallback):
            active.append(fallback)
        else:
            logger.warning(
                "Configured LLM fallback '%s' has no API key and will be skipped.",
                fallback,
            )
    return tuple(active)


def provider_model_name(provider: str) -> str:
    normalized = normalize_provider_name(provider)
    return settings.openai_model if normalized == "openai" else settings.anthropic_model


def provider_profile_model_name(provider: str) -> str:
    """Return the low-latency model reserved for CV profile extraction."""
    normalized = normalize_provider_name(provider)
    if normalized == "openai":
        return settings.openai_profile_model or settings.openai_model
    return settings.anthropic_profile_model or settings.anthropic_model


def configured_model_label() -> str:
    """Return an auditable provider/model label for reports and diagnostics."""
    return " -> ".join(
        f"{provider}:{provider_model_name(provider)}"
        for provider in active_provider_chain()
    )


def build_chat_model(provider: str, *, model_name: str | None = None):
    """Build one provider-specific LangChain chat model without silent fallback."""
    normalized = normalize_provider_name(provider)
    selected_model = model_name or provider_model_name(normalized)
    if normalized == "openai":
        return ChatOpenAI(
            model=selected_model,
            temperature=0,
            api_key=settings.require_openai_api_key(),
        )

    return ChatAnthropic(
        model=selected_model,
        temperature=0,
        api_key=settings.require_anthropic_api_key(),
    )


def _with_fallbacks(runnables: Sequence[Runnable]) -> Runnable:
    if not runnables:
        raise ValueError("At least one configured LLM provider is required.")
    primary, *fallbacks = runnables
    if not fallbacks:
        return primary
    return primary.with_fallbacks(list(fallbacks), exceptions_to_handle=(Exception,))


def _structured_model_candidates(provider: str, operation: str) -> tuple[str, ...]:
    """Choose a fast extraction model first, then the normal model as a safe fallback."""
    standard_model = provider_model_name(provider)
    if operation != _PROFILE_EXTRACTION_OPERATION:
        return (standard_model,)

    profile_model = provider_profile_model_name(provider)
    return tuple(dict.fromkeys((profile_model, standard_model)))


def get_structured_chat_model(schema: type[Any]) -> Runnable:
    """Return structured output with per-attempt provider telemetry and fallback."""
    operation = schema.__name__
    models = []
    for provider in active_provider_chain():
        for model_name in _structured_model_candidates(provider, operation):
            runnable = build_chat_model(
                provider,
                model_name=model_name,
            ).with_structured_output(schema)
            models.append(
                instrument_llm_runnable(
                    runnable,
                    provider=provider,
                    model=model_name,
                    operation=operation,
                )
            )
    return _with_fallbacks(models)


def get_tool_calling_chat_model(tools: list[BaseTool]) -> Runnable:
    """Return a tool-bound agent model with provider telemetry and fallback."""
    models = []
    for provider in active_provider_chain():
        model_name = provider_model_name(provider)
        runnable = build_chat_model(provider, model_name=model_name).bind_tools(tools)
        models.append(
            instrument_llm_runnable(
                runnable,
                provider=provider,
                model=model_name,
                operation="AgentChat",
            )
        )
    return _with_fallbacks(models)
