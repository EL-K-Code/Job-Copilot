from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any


GROUNDING_LABELS = ("supported", "unsupported", "ambiguous")


def _normalize_label(value: str) -> str:
    return value.strip().casefold()


def flatten_review_claims(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate review records and return one normalized row per candidate claim."""
    claims: list[dict[str, Any]] = []

    for record in records:
        job_id = str(record.get("job_id", "")).strip()
        if not job_id:
            raise ValueError("Every grounding review record must contain a job_id.")

        retrieved_ids = {
            str(item.get("id", "")).strip()
            for item in record.get("retrieved_memories", [])
            if str(item.get("id", "")).strip()
        }

        for claim_index, claim in enumerate(record.get("claims", []), start=1):
            claim_text = str(claim.get("claim", "")).strip()
            if not claim_text:
                raise ValueError(f"{job_id}: claim {claim_index} has no text.")

            label = _normalize_label(str(claim.get("label", "")))
            if label not in GROUNDING_LABELS:
                raise ValueError(
                    f"{job_id}: invalid label {claim.get('label')!r}; "
                    f"expected one of {GROUNDING_LABELS}."
                )

            supporting_ids = [
                str(item_id).strip()
                for item_id in claim.get("supporting_memory_ids", [])
                if str(item_id).strip()
            ]
            unknown_ids = sorted(set(supporting_ids) - retrieved_ids)
            if unknown_ids:
                raise ValueError(
                    f"{job_id}: claim references memories that were not retrieved: "
                    f"{unknown_ids}."
                )
            if label == "supported" and not supporting_ids:
                raise ValueError(
                    f"{job_id}: supported claims require at least one supporting memory."
                )
            if label == "unsupported" and supporting_ids:
                raise ValueError(
                    f"{job_id}: unsupported claims must not list supporting memories."
                )

            claims.append(
                {
                    "job_id": job_id,
                    "claim": claim_text,
                    "label": label,
                    "supporting_memory_ids": supporting_ids,
                    "reviewer": str(claim.get("reviewer", "")).strip(),
                }
            )

    return claims


def summarize_grounding_reviews(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute system-level grounding rates from human-reviewed email claims."""
    claims = flatten_review_claims(records)
    counts = Counter(claim["label"] for claim in claims)
    total = len(claims)

    rates = {
        f"{label}_rate": counts[label] / total if total else 0.0
        for label in GROUNDING_LABELS
    }

    by_job_counts: dict[str, Counter] = defaultdict(Counter)
    for claim in claims:
        by_job_counts[claim["job_id"]][claim["label"]] += 1

    by_job = {}
    for job_id, job_counts in sorted(by_job_counts.items()):
        job_total = sum(job_counts.values())
        by_job[job_id] = {
            "number_of_claims": job_total,
            "counts": {
                label: job_counts[label]
                for label in GROUNDING_LABELS
            },
            "unsupported_claim_rate": (
                job_counts["unsupported"] / job_total if job_total else 0.0
            ),
        }

    return {
        "number_of_reviewed_jobs": len(by_job),
        "number_of_claims": total,
        "counts": {label: counts[label] for label in GROUNDING_LABELS},
        **rates,
        "unsupported_claim_rate": rates["unsupported_rate"],
        "by_job": by_job,
        "claims": claims,
    }
