from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI

from app.config import settings

SUPPORTED_LLM_PROVIDERS = {"anthropic", "openai"}


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


def configured_model_label() -> str:
    """Return an auditable provider/model label for reports and diagnostics."""
    labels = []
    for provider in configured_provider_chain():
        model = settings.openai_model if provider == "openai" else settings.anthropic_model
        labels.append(f"{provider}:{model}")
    return " -> ".join(labels)


def build_chat_model(provider: str):
    """Build one provider-specific LangChain chat model without silent fallback."""
    normalized = normalize_provider_name(provider)
    if normalized == "openai":
        return ChatOpenAI(
            model=settings.openai_model,
            temperature=0,
            api_key=settings.require_openai_api_key(),
        )

    return ChatAnthropic(
        model=settings.anthropic_model,
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


def get_structured_chat_model(schema: type[Any]) -> Runnable:
    """Return a structured-output runnable with optional cross-provider fallback."""
    models = [
        build_chat_model(provider).with_structured_output(schema)
        for provider in configured_provider_chain()
    ]
    return _with_fallbacks(models)


def get_tool_calling_chat_model(tools: list[BaseTool]) -> Runnable:
    """Return a tool-bound agent model with optional cross-provider fallback."""
    models = [
        build_chat_model(provider).bind_tools(tools)
        for provider in configured_provider_chain()
    ]
    return _with_fallbacks(models)
