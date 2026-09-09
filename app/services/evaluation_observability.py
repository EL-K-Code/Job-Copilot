from __future__ import annotations

import json
from pathlib import Path
from statistics import mean
from typing import Any

from app.evaluation import normalize_evaluation_item
from app.services.llm_telemetry import summarize_llm_events


_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_PUBLISHED_RETRIEVAL_SUMMARY = (
    _PROJECT_ROOT / "evaluation" / "published" / "retrieval_v2_summary.json"
)
_JOB_TERM_FIELDS = (
    "required_skills",
    "preferred_skills",
    "tools_and_stack",
    "domain_focus",
)


def _ordered_unique(values: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = " ".join(str(raw).strip().split())
        key = normalize_evaluation_item(value)
        if not value or not key or key in seen:
            continue
        seen.add(key)
        output.append(value)
    return output


def _explicit_job_terms(job_analysis: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for field in _JOB_TERM_FIELDS:
        values.extend(str(item) for item in job_analysis.get(field, []) if str(item).strip())
    return _ordered_unique(values)


def summarize_retrieval_trace(memory_records: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize retrieval provenance without interpreting model scores as probabilities."""
    if not memory_records:
        return {
            "evidence_count": 0,
            "strategy": "unknown",
            "reranker_applied": False,
            "reranked_evidence_count": 0,
            "dense_evidence_count": 0,
            "sparse_evidence_count": 0,
            "dense_and_sparse_count": 0,
            "dense_only_count": 0,
            "sparse_only_count": 0,
            "mean_final_rank": None,
        }

    strategies = _ordered_unique(
        [str(record.get("retrieval_strategy", "")) for record in memory_records]
    )
    dense = [record for record in memory_records if record.get("retrieval_dense_rank") is not None]
    sparse = [record for record in memory_records if record.get("retrieval_sparse_rank") is not None]
    both = [
        record
        for record in memory_records
        if record.get("retrieval_dense_rank") is not None
        and record.get("retrieval_sparse_rank") is not None
    ]
    dense_only = [
        record
        for record in memory_records
        if record.get("retrieval_dense_rank") is not None
        and record.get("retrieval_sparse_rank") is None
    ]
    sparse_only = [
        record
        for record in memory_records
        if record.get("retrieval_sparse_rank") is not None
        and record.get("retrieval_dense_rank") is None
    ]
    reranked = [
        record
        for record in memory_records
        if bool(record.get("retrieval_reranker_applied"))
    ]
    final_ranks = [
        int(record["retrieval_final_rank"])
        for record in memory_records
        if isinstance(record.get("retrieval_final_rank"), int)
    ]

    return {
        "evidence_count": len(memory_records),
        "strategy": " + ".join(strategies) if strategies else "dense_faiss",
        "reranker_applied": bool(reranked),
        "reranked_evidence_count": len(reranked),
        "dense_evidence_count": len(dense),
        "sparse_evidence_count": len(sparse),
        "dense_and_sparse_count": len(both),
        "dense_only_count": len(dense_only),
        "sparse_only_count": len(sparse_only),
        "mean_final_rank": mean(final_ranks) if final_ranks else None,
    }


def summarize_grounding_integrity(
    *,
    job_analysis: dict[str, Any],
    email_draft: dict[str, Any],
    application_pack: dict[str, Any],
    memory_records: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compute deterministic claim/evidence integrity metrics for one generated pack."""
    memory_ids = {
        str(record.get("id", "")).strip()
        for record in memory_records
        if str(record.get("id", "")).strip()
    }
    claims = list(email_draft.get("claim_evidence", []) or [])

    grounded_claims = 0
    unsupported_claims = 0
    partially_supported_claims = 0
    unknown_memory_ids: list[str] = []
    covered_job_terms: list[str] = []

    for claim in claims:
        supporting_ids = _ordered_unique(
            [str(item) for item in claim.get("supporting_memory_ids", [])]
        )
        known = [memory_id for memory_id in supporting_ids if memory_id in memory_ids]
        unknown = [memory_id for memory_id in supporting_ids if memory_id not in memory_ids]
        unknown_memory_ids.extend(unknown)

        if known:
            grounded_claims += 1
            if unknown:
                partially_supported_claims += 1
        else:
            unsupported_claims += 1

        covered_job_terms.extend(
            str(item)
            for item in claim.get("aligned_job_terms", [])
            if str(item).strip()
        )

    explicit_terms = _explicit_job_terms(job_analysis)
    explicit_by_normalized = {
        normalize_evaluation_item(term): term
        for term in explicit_terms
        if normalize_evaluation_item(term)
    }
    covered_normalized = {
        normalize_evaluation_item(term)
        for term in covered_job_terms
        if normalize_evaluation_item(term) in explicit_by_normalized
    }

    claim_count = len(claims)
    evidence_coverage = grounded_claims / claim_count if claim_count else 1.0
    job_term_evidence_coverage = (
        len(covered_normalized) / len(explicit_by_normalized)
        if explicit_by_normalized
        else 1.0
    )
    unknown_ids = _ordered_unique(unknown_memory_ids)

    return {
        "claim_count": claim_count,
        "grounded_claims": grounded_claims,
        "unsupported_claims": unsupported_claims,
        "partially_supported_claims": partially_supported_claims,
        "unknown_memory_id_count": len(unknown_ids),
        "unknown_memory_ids": unknown_ids,
        "evidence_coverage": evidence_coverage,
        "grounding_integrity_pass": unsupported_claims == 0 and not unknown_ids,
        "explicit_job_term_count": len(explicit_by_normalized),
        "covered_job_term_count": len(covered_normalized),
        "job_term_evidence_coverage": job_term_evidence_coverage,
        "missing_job_term_count": len(application_pack.get("missing_job_terms", []) or []),
    }


def summarize_application_observability(results: dict[str, Any]) -> dict[str, Any]:
    """Build the privacy-safe observability payload shown in the evaluation dashboard."""
    memory_records = list(results.get("retrieved_memory_records", []) or [])
    llm_events = list(results.get("llm_telemetry", []) or [])
    return {
        "grounding": summarize_grounding_integrity(
            job_analysis=dict(results.get("job_analysis", {}) or {}),
            email_draft=dict(results.get("email_draft", {}) or {}),
            application_pack=dict(results.get("application_pack", {}) or {}),
            memory_records=memory_records,
        ),
        "retrieval": summarize_retrieval_trace(memory_records),
        "llm": summarize_llm_events(llm_events),
    }


def load_published_retrieval_summary(
    path: Path | None = None,
) -> dict[str, Any] | None:
    """Load a committed synthetic retrieval benchmark summary when available."""
    target = path or _PUBLISHED_RETRIEVAL_SUMMARY
    if not target.exists():
        return None
    payload = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Published retrieval summary must be a JSON object.")
    return payload
