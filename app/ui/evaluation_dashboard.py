from __future__ import annotations

from html import escape
from typing import Any

import streamlit as st

from app.services.evaluation_observability import (
    load_published_retrieval_summary,
    summarize_application_observability,
)


_STRATEGY_LABELS = {
    "dense": "Dense FAISS",
    "hybrid": "FAISS + BM25 + RRF",
    "hybrid_rerank": "Hybrid + cross-encoder",
}


def _pct(value: Any) -> str:
    try:
        return f"{float(value) * 100:.1f}%"
    except (TypeError, ValueError):
        return "—"


def _seconds(milliseconds: Any) -> str:
    try:
        return f"{float(milliseconds) / 1000:.2f}s"
    except (TypeError, ValueError):
        return "—"


def _render_runtime_quality(results: dict[str, Any]) -> None:
    summary = summarize_application_observability(results)
    grounding = summary["grounding"]
    retrieval = summary["retrieval"]
    llm = summary["llm"]

    st.markdown("### Current application run")
    st.caption(
        "Deterministic observability for the application currently held in this browser session. "
        "These diagnostics add no extra LLM call and are not a recruiter-outcome score."
    )

    quality_col, unsupported_col, offer_col, missing_col = st.columns(4)
    quality_col.metric("Evidence coverage", _pct(grounding["evidence_coverage"]))
    unsupported_col.metric("Unsupported claims", grounding["unsupported_claims"])
    offer_col.metric(
        "Offer-term evidence coverage",
        _pct(grounding["job_term_evidence_coverage"]),
    )
    missing_col.metric("Uncovered job terms", grounding["missing_job_term_count"])

    if grounding["grounding_integrity_pass"]:
        st.success(
            "Grounding integrity passed: every factual email claim points to retrieved verified profile evidence."
        )
    else:
        st.error(
            "Grounding integrity needs review: at least one claim has missing or unknown supporting evidence."
        )
        if grounding["unknown_memory_ids"]:
            st.caption("Unknown memory IDs: " + ", ".join(grounding["unknown_memory_ids"]))

    retrieval_tab, llm_tab = st.tabs(["Retrieval trace", "LLM runtime"])
    with retrieval_tab:
        left, middle, right, fourth = st.columns(4)
        left.metric("Evidence returned", retrieval["evidence_count"])
        middle.metric("Dense + sparse", retrieval["dense_and_sparse_count"])
        right.metric("Sparse-only recovered", retrieval["sparse_only_count"])
        fourth.metric(
            "Cross-encoder",
            "Applied" if retrieval["reranker_applied"] else "Not applied",
        )
        st.caption(f"Production retrieval strategy: {retrieval['strategy']}")

        trace_rows = []
        for record in results.get("retrieved_memory_records", []) or []:
            trace_rows.append(
                {
                    "memory_id": str(record.get("id", "")),
                    "type": str(record.get("type", "")),
                    "final_rank": record.get("retrieval_final_rank"),
                    "dense_rank": record.get("retrieval_dense_rank"),
                    "bm25_rank": record.get("retrieval_sparse_rank"),
                    "rrf_rank": record.get("retrieval_fusion_rank"),
                    "reranked": bool(record.get("retrieval_reranker_applied")),
                }
            )
        if trace_rows:
            st.dataframe(trace_rows, use_container_width=True, hide_index=True)
        else:
            st.info("No retrieval provenance is available for this run.")

        st.caption(
            "Cross-encoder and RRF scores are ranking signals, not calibrated probabilities; "
            "the dashboard therefore exposes ranks rather than turning them into a fake confidence score."
        )

    with llm_tab:
        call_col, latency_col, token_col, fallback_col = st.columns(4)
        call_col.metric("Successful LLM calls", llm["successful_calls"])
        latency_col.metric("LLM wall time", _seconds(llm["total_duration_ms"]))
        token_col.metric(
            "Tokens",
            f"{int(llm['total_tokens']):,}" if isinstance(llm.get("total_tokens"), int) else "Unavailable",
        )
        fallback_col.metric("Provider fallback", "Used" if llm["fallback_used"] else "No")

        st.write(
            f"**Final provider/model:** {str(llm.get('final_provider') or 'unknown').title()} · "
            f"{llm.get('final_model') or 'unknown'}"
        )
        st.write(
            f"**Attempt success rate:** {_pct(llm['success_rate'])} · "
            f"**P95 successful-call latency:** {_seconds(llm['p95_success_latency_ms'])}"
        )

        operation_rows = []
        for operation, metrics in llm.get("operation_breakdown", {}).items():
            operation_rows.append(
                {
                    "operation": operation,
                    "attempts": metrics.get("attempts", 0),
                    "success": metrics.get("successful_calls", 0),
                    "errors": metrics.get("failed_attempts", 0),
                    "latency_s": round(float(metrics.get("duration_ms", 0) or 0) / 1000, 3),
                    "input_tokens": metrics.get("input_tokens") if metrics.get("token_usage_available") else None,
                    "output_tokens": metrics.get("output_tokens") if metrics.get("token_usage_available") else None,
                }
            )
        if operation_rows:
            st.dataframe(operation_rows, use_container_width=True, hide_index=True)

        st.caption(
            "Telemetry contains provider/model, latency, token counts when exposed by the provider, "
            "and error class only. Prompts, job text, CV facts, generated content, API keys and OAuth tokens are excluded."
        )


def _render_published_benchmark() -> None:
    st.markdown("### Synthetic retrieval benchmark")
    report = load_published_retrieval_summary()
    if not report:
        st.info(
            "The comparative retrieval benchmark is wired into CI but no compact published summary "
            "has been committed yet. JobCopilot will not claim a retrieval gain before that run is measured."
        )
        return

    latency_scope = str(report.get("latency_scope", "unknown")).replace("_", " ")
    st.caption(
        f"{int(report.get('number_of_cases', 0))} labeled synthetic queries · "
        f"top-{int(report.get('k', 5))} retrieval · same fictional public profile for every strategy · "
        f"latency: {latency_scope}."
    )

    rows = []
    for strategy, metrics in report.get("strategies", {}).items():
        rows.append(
            {
                "strategy": _STRATEGY_LABELS.get(strategy, strategy),
                "MRR": round(float(metrics.get("mrr", 0.0)), 4),
                "Recall@1": round(float(metrics.get("recall@1", 0.0)), 4),
                "Recall@3": round(float(metrics.get("recall@3", 0.0)), 4),
                "Recall@5": round(float(metrics.get("recall@5", 0.0)), 4),
                "NDCG@5": round(float(metrics.get("ndcg@5", 0.0)), 4),
                "Mean latency (ms)": round(float(metrics.get("mean_latency_ms", 0.0)), 1),
                "P95 latency (ms)": round(float(metrics.get("p95_latency_ms", 0.0)), 1),
            }
        )
    if rows:
        st.dataframe(rows, use_container_width=True, hide_index=True)

    best = report.get("best_by_metric", {})
    key_metrics = ("mrr", "recall@5", "ndcg@5", "mean_latency_ms")
    if best:
        best_text = " · ".join(
            f"{escape(metric)}: {_STRATEGY_LABELS.get(str(best[metric]), str(best[metric]))}"
            for metric in key_metrics
            if metric in best
        )
        if best_text:
            st.caption("Best measured strategy by selected metric · " + best_text)

    deltas = report.get("delta_vs_dense", {})
    rerank_delta = deltas.get("hybrid_rerank", {}) if isinstance(deltas, dict) else {}
    if rerank_delta:
        st.write(
            "**Hybrid + reranker vs dense baseline:** "
            + ", ".join(
                [
                    f"MRR {float(rerank_delta.get('mrr', 0.0)):+.4f}",
                    f"Recall@5 {float(rerank_delta.get('recall@5', 0.0)):+.4f}",
                    f"NDCG@5 {float(rerank_delta.get('ndcg@5', 0.0)):+.4f}",
                    f"mean latency {float(rerank_delta.get('mean_latency_ms', 0.0)):+.1f} ms",
                ]
            )
        )

    st.warning(
        "Benchmark results are synthetic engineering regression metrics, not evidence that recruiters "
        "will respond more often or that the system improves real hiring outcomes."
    )


def render_evaluation_dashboard(_user: dict[str, str]) -> None:
    """Render the read-only AI quality and observability workspace."""
    st.markdown("## AI Evaluation")
    st.caption(
        "Measure retrieval quality, grounding integrity and runtime behavior instead of treating a fluent LLM response as proof of quality."
    )

    results = st.session_state.get("results")
    if results:
        _render_runtime_quality(results)
    else:
        st.info(
            "Run an application analysis first. Its privacy-safe retrieval, grounding and LLM diagnostics will appear here."
        )

    st.divider()
    _render_published_benchmark()

    with st.expander("What these metrics mean"):
        st.markdown(
            """
- **Evidence coverage**: share of factual email claims that reference at least one retrieved verified memory ID.
- **Offer-term evidence coverage**: share of explicit skills/tools/domain terms in the offer that are aligned to the selected evidence. It is not a candidate-fit probability.
- **Unsupported claims**: factual claims whose referenced evidence is absent from the retrieved profile context.
- **Recall@K**: fraction of labeled relevant memories found in the first K retrieval results.
- **MRR**: rewards putting the first relevant memory near the top of the ranking.
- **NDCG@K**: measures ranking quality while rewarding relevant evidence higher in the list.
- **Retrieval latency**: warm-process timing after one strategy-specific warm-up, so one-off model loading is not mixed into steady-state ranking latency.
- **LLM runtime metrics**: provider attempts, latency, token usage when available, and fallback behavior without retaining prompt or CV text.
            """
        )
