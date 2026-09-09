from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from app.config import settings


ModelTier = Literal["economy", "standard", "strong"]
RoutingMode = Literal["adaptive", "single"]


@dataclass(frozen=True)
class ModelRouteDecision:
    operation: str
    tier: ModelTier
    reason: str
    escalated: bool = False


_OPERATION_DEFAULT_TIERS: dict[str, ModelTier] = {
    "ProfileExtraction": "economy",
    "JobAnalysis": "economy",
    "EmailEvidenceSelection": "economy",
    "MatchInsight": "standard",
    "AgentChat": "standard",
}


def routing_mode() -> RoutingMode:
    value = str(getattr(settings, "llm_routing_mode", "adaptive")).strip().lower()
    return "single" if value == "single" else "adaptive"


def default_tier_for_operation(operation: str) -> ModelTier:
    if routing_mode() == "single":
        return "standard"
    return _OPERATION_DEFAULT_TIERS.get(operation, "standard")


def route_operation(
    operation: str,
    *,
    force_tier: ModelTier | None = None,
    escalated: bool = False,
    reason: str = "",
) -> ModelRouteDecision:
    if force_tier is not None:
        tier = force_tier
        resolved_reason = reason or f"explicit_{force_tier}_route"
    elif escalated:
        tier = "strong"
        resolved_reason = reason or "deterministic_quality_gate_failed"
    else:
        tier = default_tier_for_operation(operation)
        resolved_reason = reason or f"operation_policy:{operation}"
    return ModelRouteDecision(
        operation=operation,
        tier=tier,
        reason=resolved_reason,
        escalated=escalated,
    )


def route_job_analysis(job_text: str) -> ModelRouteDecision:
    """Route long/complex offers to the standard tier without using another LLM call."""
    if routing_mode() == "single":
        return route_operation("JobAnalysis", force_tier="standard", reason="single_model_mode")

    threshold = int(getattr(settings, "llm_routing_complex_job_chars", 6000))
    normalized = " ".join(str(job_text).split())
    if len(normalized) >= threshold:
        return route_operation(
            "JobAnalysis",
            force_tier="standard",
            reason=f"complex_offer_chars>={threshold}",
        )
    return route_operation("JobAnalysis")


def provider_model_for_tier(
    provider: str,
    tier: ModelTier,
    *,
    settings_obj: Any | None = None,
) -> str:
    """Resolve one logical tier from the settings object used by the provider factory."""
    active_settings = settings if settings_obj is None else settings_obj
    normalized = provider.strip().lower()
    if normalized == "openai":
        if tier == "economy":
            return (
                getattr(active_settings, "openai_economy_model", "")
                or getattr(active_settings, "openai_profile_model", "")
                or active_settings.openai_model
            )
        if tier == "strong":
            return (
                getattr(active_settings, "openai_strong_model", "")
                or active_settings.openai_model
            )
        return active_settings.openai_model

    if normalized == "anthropic":
        if tier == "economy":
            return (
                getattr(active_settings, "anthropic_economy_model", "")
                or getattr(active_settings, "anthropic_profile_model", "")
                or active_settings.anthropic_model
            )
        if tier == "strong":
            return (
                getattr(active_settings, "anthropic_strong_model", "")
                or active_settings.anthropic_model
            )
        return active_settings.anthropic_model

    raise ValueError(f"Unsupported LLM provider '{provider}'.")


def stronger_tiers(tier: ModelTier) -> tuple[ModelTier, ...]:
    if routing_mode() == "single":
        return ("standard",)
    if tier == "economy":
        return ("economy", "standard", "strong")
    if tier == "standard":
        return ("standard", "strong")
    return ("strong",)
