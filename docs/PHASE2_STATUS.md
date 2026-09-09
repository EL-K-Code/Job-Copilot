# Phase 2 — Evaluation & Observability status

Phase 2 is considered complete when JobCopilot can demonstrate the following without relying on subjective screenshots or unverified claims:

- deterministic runtime grounding-integrity metrics;
- auditable retrieval provenance;
- privacy-safe LLM runtime telemetry;
- comparative dense / hybrid / reranked retrieval benchmarking;
- warm-process latency reporting;
- paired case-level uncertainty against the dense baseline;
- a dedicated Streamlit AI Evaluation workspace;
- CI coverage for evaluation summaries and retrieval-regression execution;
- explicit separation between engineering regression metrics and recruiter/hiring outcomes.

The implementation intentionally avoids inventing a single opaque "AI quality score". Retrieval quality, grounding integrity and runtime behavior remain separate measurable dimensions.
