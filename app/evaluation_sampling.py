from __future__ import annotations

from collections import OrderedDict
from typing import Any, Literal


SamplingMode = Literal["head", "stratified"]


def select_review_cases(
    cases: list[dict[str, Any]],
    *,
    limit: int,
    sampling: SamplingMode = "stratified",
) -> list[dict[str, Any]]:
    """Select deterministic grounding cases, favoring category coverage for small runs."""
    if limit < 0:
        raise ValueError("limit cannot be negative.")
    if limit == 0 or limit >= len(cases):
        return list(cases)
    if sampling == "head":
        return list(cases[:limit])
    if sampling != "stratified":
        raise ValueError(f"Unsupported sampling mode: {sampling}")

    grouped: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    for case in cases:
        category = str(case.get("category", "unknown")).strip() or "unknown"
        grouped.setdefault(category, []).append(case)

    selected: list[dict[str, Any]] = []
    round_index = 0
    while len(selected) < limit:
        added_this_round = False
        for category_cases in grouped.values():
            if round_index >= len(category_cases):
                continue
            selected.append(category_cases[round_index])
            added_this_round = True
            if len(selected) >= limit:
                break
        if not added_this_round:
            break
        round_index += 1

    return selected
