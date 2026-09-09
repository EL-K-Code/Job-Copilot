from __future__ import annotations

from types import SimpleNamespace

from app.services import model_routing


def _settings(**overrides):
    values = {
        "llm_routing_mode": "adaptive",
        "llm_routing_complex_job_chars": 100,
        "openai_model": "gpt-standard",
        "openai_profile_model": "gpt-profile",
        "openai_economy_model": "gpt-economy",
        "openai_strong_model": "gpt-strong",
        "anthropic_model": "claude-standard",
        "anthropic_profile_model": "claude-profile",
        "anthropic_economy_model": "claude-economy",
        "anthropic_strong_model": "claude-strong",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_operation_policy_uses_smallest_expected_tier(monkeypatch):
    monkeypatch.setattr(model_routing, "settings", _settings())

    assert model_routing.route_operation("ProfileExtraction").tier == "economy"
    assert model_routing.route_operation("JobAnalysis").tier == "economy"
    assert model_routing.route_operation("EmailEvidenceSelection").tier == "economy"
    assert model_routing.route_operation("MatchInsight").tier == "standard"
    assert model_routing.route_operation("AgentChat").tier == "standard"


def test_deterministic_quality_failure_escalates_to_strong(monkeypatch):
    monkeypatch.setattr(model_routing, "settings", _settings())
    decision = model_routing.route_operation(
        "MatchInsight",
        escalated=True,
        reason="claim_evidence_validation_failed",
    )
    assert decision.tier == "strong"
    assert decision.escalated is True
    assert decision.reason == "claim_evidence_validation_failed"


def test_complex_job_offer_routes_to_standard_without_classifier_call(monkeypatch):
    monkeypatch.setattr(model_routing, "settings", _settings(llm_routing_complex_job_chars=20))
    decision = model_routing.route_job_analysis("x" * 25)
    assert decision.tier == "standard"
    assert "complex_offer_chars" in decision.reason


def test_single_mode_preserves_standard_only_behavior(monkeypatch):
    monkeypatch.setattr(model_routing, "settings", _settings(llm_routing_mode="single"))
    assert model_routing.route_operation("ProfileExtraction").tier == "standard"
    assert model_routing.stronger_tiers("economy") == ("standard",)


def test_provider_model_resolution_is_explicit_by_tier(monkeypatch):
    monkeypatch.setattr(model_routing, "settings", _settings())
    assert model_routing.provider_model_for_tier("openai", "economy") == "gpt-economy"
    assert model_routing.provider_model_for_tier("openai", "standard") == "gpt-standard"
    assert model_routing.provider_model_for_tier("openai", "strong") == "gpt-strong"
    assert model_routing.provider_model_for_tier("anthropic", "strong") == "claude-strong"
