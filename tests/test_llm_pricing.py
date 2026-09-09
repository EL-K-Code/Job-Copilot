from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services import llm_pricing


def _settings(raw: str, version: str = "test-rates"):
    return SimpleNamespace(llm_pricing_json=raw, llm_pricing_version=version)


def test_empty_pricing_catalog_disables_cost_estimation(monkeypatch):
    monkeypatch.setattr(llm_pricing, "settings", _settings(""))
    assert llm_pricing.load_pricing_catalog() == {}
    assert (
        llm_pricing.estimate_call_cost_usd(
            provider="openai",
            model="gpt-test",
            input_tokens=100,
            output_tokens=20,
        )
        is None
    )


def test_explicit_rates_compute_token_cost(monkeypatch):
    monkeypatch.setattr(
        llm_pricing,
        "settings",
        _settings(
            '{"openai:gpt-test":{"input_per_million_usd":2.0,"output_per_million_usd":8.0}}'
        ),
    )
    cost = llm_pricing.estimate_call_cost_usd(
        provider="OpenAI",
        model="GPT-Test",
        input_tokens=1_000_000,
        output_tokens=500_000,
    )
    assert cost == pytest.approx(6.0)


def test_invalid_catalog_fails_loudly(monkeypatch):
    monkeypatch.setattr(llm_pricing, "settings", _settings("not-json"))
    with pytest.raises(ValueError, match="valid JSON"):
        llm_pricing.load_pricing_catalog()


def test_pricing_version_is_explicit(monkeypatch):
    monkeypatch.setattr(llm_pricing, "settings", _settings("", version="2026-09-reviewed"))
    assert llm_pricing.pricing_version() == "2026-09-reviewed"
