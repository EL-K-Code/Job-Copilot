from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from app.config import settings


@dataclass(frozen=True)
class ModelPricing:
    input_per_million_usd: float
    output_per_million_usd: float


def pricing_version() -> str:
    return str(getattr(settings, "llm_pricing_version", "unconfigured")).strip() or "unconfigured"


def _raw_catalog() -> str:
    return str(getattr(settings, "llm_pricing_json", "")).strip()


def load_pricing_catalog() -> dict[str, ModelPricing]:
    """Load explicit provider/model rates. No provider price is hard-coded in the app."""
    raw = _raw_catalog()
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("LLM_PRICING_JSON must be valid JSON.") from exc
    if not isinstance(payload, dict):
        raise ValueError("LLM_PRICING_JSON must be a JSON object.")

    catalog: dict[str, ModelPricing] = {}
    for key, value in payload.items():
        if not isinstance(value, dict):
            raise ValueError(f"Pricing entry '{key}' must be a JSON object.")
        try:
            input_rate = float(value["input_per_million_usd"])
            output_rate = float(value["output_per_million_usd"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(
                f"Pricing entry '{key}' must define numeric input_per_million_usd and output_per_million_usd."
            ) from exc
        if input_rate < 0 or output_rate < 0:
            raise ValueError(f"Pricing entry '{key}' cannot contain negative rates.")
        catalog[str(key).strip().lower()] = ModelPricing(
            input_per_million_usd=input_rate,
            output_per_million_usd=output_rate,
        )
    return catalog


def pricing_key(provider: str, model: str) -> str:
    return f"{provider.strip().lower()}:{model.strip().lower()}"


def estimate_call_cost_usd(
    *,
    provider: str,
    model: str,
    input_tokens: int | None,
    output_tokens: int | None,
    catalog: dict[str, ModelPricing] | None = None,
) -> float | None:
    if not isinstance(input_tokens, int) or not isinstance(output_tokens, int):
        return None
    rates = (catalog or load_pricing_catalog()).get(pricing_key(provider, model))
    if rates is None:
        return None
    return (
        input_tokens * rates.input_per_million_usd
        + output_tokens * rates.output_per_million_usd
    ) / 1_000_000


def estimate_event_cost_usd(
    event: dict[str, Any],
    *,
    catalog: dict[str, ModelPricing] | None = None,
) -> float | None:
    if event.get("status") != "success":
        return 0.0
    return estimate_call_cost_usd(
        provider=str(event.get("provider", "")),
        model=str(event.get("model", "")),
        input_tokens=event.get("input_tokens"),
        output_tokens=event.get("output_tokens"),
        catalog=catalog,
    )
