from __future__ import annotations

from types import SimpleNamespace

import pytest
from langchain_core.runnables import RunnableLambda

from app.services import model_provider


def _settings(**overrides):
    values = {
        "llm_provider": "openai",
        "llm_fallback_provider": "anthropic",
        "openai_api_key": "openai-secret",
        "openai_model": "gpt-test",
        "anthropic_api_key": "anthropic-secret",
        "anthropic_model": "claude-test",
    }
    values.update(overrides)
    values["require_openai_api_key"] = lambda: (
        values["openai_api_key"]
        if values["openai_api_key"]
        else (_ for _ in ()).throw(RuntimeError("missing openai"))
    )
    values["require_anthropic_api_key"] = lambda: (
        values["anthropic_api_key"]
        if values["anthropic_api_key"]
        else (_ for _ in ()).throw(RuntimeError("missing anthropic"))
    )
    return SimpleNamespace(**values)


def test_provider_names_are_strictly_validated():
    assert model_provider.normalize_provider_name(" OpenAI ") == "openai"
    with pytest.raises(ValueError, match="Unsupported LLM provider"):
        model_provider.normalize_provider_name("unknown-provider")


def test_configured_chain_deduplicates_primary_and_fallback(monkeypatch):
    monkeypatch.setattr(
        model_provider,
        "settings",
        _settings(llm_provider="openai", llm_fallback_provider="OPENAI"),
    )
    assert model_provider.configured_provider_chain() == ("openai",)


def test_missing_optional_fallback_key_does_not_block_primary(monkeypatch):
    monkeypatch.setattr(
        model_provider,
        "settings",
        _settings(anthropic_api_key=""),
    )
    assert model_provider.active_provider_chain() == ("openai",)


def test_missing_primary_key_fails_before_any_request(monkeypatch):
    monkeypatch.setattr(
        model_provider,
        "settings",
        _settings(openai_api_key=""),
    )
    with pytest.raises(RuntimeError, match="missing openai"):
        model_provider.active_provider_chain()


def test_configured_model_label_records_provider_order(monkeypatch):
    monkeypatch.setattr(model_provider, "settings", _settings())
    assert (
        model_provider.configured_model_label()
        == "openai:gpt-test -> anthropic:claude-test"
    )


def test_runnable_fallback_uses_secondary_provider_after_primary_failure():
    primary = RunnableLambda(
        lambda _input: (_ for _ in ()).throw(RuntimeError("primary unavailable"))
    )
    fallback = RunnableLambda(lambda value: f"fallback:{value}")

    runnable = model_provider._with_fallbacks([primary, fallback])
    assert runnable.invoke("job") == "fallback:job"


def test_structured_factory_builds_models_in_configured_order(monkeypatch):
    calls = []

    class FakeModel:
        def __init__(self, provider):
            self.provider = provider

        def with_structured_output(self, schema):
            calls.append((self.provider, schema.__name__))
            return RunnableLambda(lambda _messages: self.provider)

    monkeypatch.setattr(model_provider, "settings", _settings())
    monkeypatch.setattr(
        model_provider,
        "build_chat_model",
        lambda provider: FakeModel(provider),
    )

    class ExampleSchema:
        pass

    runnable = model_provider.get_structured_chat_model(ExampleSchema)
    assert runnable.invoke([]) == "openai"
    assert calls == [("openai", "ExampleSchema"), ("anthropic", "ExampleSchema")]
