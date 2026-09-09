# JobCopilot Premium AI Engineering Roadmap

JobCopilot is intentionally evolving from a prompt-driven job assistant into an **evidence-grounded, evaluated, human-supervised agentic system**. The goal is not to imitate a general chat product. The goal is to make the engineering choices around retrieval, grounding, orchestration, evaluation and external actions explicit and measurable.

## Phase 1 — Hybrid evidence retrieval + reranking

Status: **implemented and benchmarked**.

Production retrieval path:

```text
verified profile memories
        │
        ├── dense retrieval: all-MiniLM-L6-v2 + FAISS
        │
        └── sparse retrieval: deterministic BM25
                     │
                     ▼
             reciprocal-rank fusion
                     │
                     ▼
             cross-encoder reranker
                     │
                     ▼
             top verified evidence
```

Engineering guarantees:

- every retrieval path remains tenant-scoped;
- stable memory IDs and evidence provenance are preserved;
- dense rank/distance, sparse rank/score, RRF rank/score and reranker score are auditable;
- cross-encoder failure falls back safely to deterministic fused retrieval;
- dense FAISS remains available as a benchmark baseline;
- dense, hybrid and hybrid+reranker are compared on the same labeled retrieval cases;
- quality improvements are claimed only where the benchmark demonstrates them.

Primary metrics: MRR, Recall@1/3/5, NDCG@1/3/5 and warm-process retrieval latency.

### Measured retrieval trade-off — v2 synthetic benchmark

The first comparative run uses 20 labeled synthetic profile-memory queries and top-5 retrieval. Latency is measured after one strategy-specific warm-up, so cold model-loading time is excluded.

| Strategy | MRR | Recall@1 | Recall@3 | Recall@5 | NDCG@5 | Mean latency |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Dense FAISS | **1.000** | **0.825** | 0.975 | 0.975 | **0.9766** | **11.1 ms** |
| FAISS + BM25 + RRF | 0.975 | 0.800 | 0.975 | 0.975 | 0.9613 | 12.0 ms |
| Hybrid + cross-encoder | 0.975 | 0.775 | **1.000** | **1.000** | 0.9655 | 75.0 ms |

The result is intentionally treated as a **trade-off, not a universal win**. Dense FAISS leads MRR, Recall@1, NDCG@5 and latency on this small benchmark, while the cross-encoder path raises Recall@3 and Recall@5 to 1.0. Relative to dense, the reranked path gains +0.025 Recall@5 but loses 0.025 MRR and about 0.011 NDCG@5 while adding roughly 64 ms mean warm latency.

This is exactly why the retrieval strategies remain configurable: later evaluation can decide whether maximum evidence recall, top-rank quality or latency is the right objective for a given workflow.

## Phase 2 — Evaluation and observability layer

Status: **implemented and validated in CI**.

The product has a dedicated **AI Evaluation** surface separating runtime diagnostics from offline synthetic benchmark evidence.

Runtime metrics include grounding integrity, evidence coverage, retrieval provenance, LLM provider/model attempts, latency and token usage when exposed. Offline evaluation includes MRR, Recall@K, NDCG@K, paired bootstrap uncertainty and retrieval latency across dense, hybrid and reranked strategies.

Engineering constraints:

- the dashboard adds no extra LLM call merely to score a run;
- ranking scores are not presented as fake probabilities;
- prompts, CV facts, job text, generated content, API keys and OAuth tokens are excluded from telemetry;
- published benchmark summaries contain aggregate metrics only;
- synthetic evaluation is never presented as recruiter-outcome evidence.

## Phase 3 — Stateful application agent with human approval gates

Status: **implemented and validated in CI**.

```text
DISCOVERED
   ↓
ANALYZED
   ↓
READY_TO_APPLY
   ↓
AWAITING_APPROVAL
   ↓
APPLIED
   ↓
FOLLOW_UP_DUE
   ↓
INTERVIEW / REJECTED / OFFER / CLOSED
```

The LLM can analyze and prepare work, while consequential lifecycle facts remain deterministic and human-supervised.

Implemented guarantees:

- explicit persisted state transitions;
- human confirmation before `APPLIED`;
- user-reported confirmation before interview/rejection/offer outcomes;
- append-only workflow audit events;
- idempotency keys for workflow-bound Gmail and Calendar side effects;
- Gmail draft creation does not imply submission;
- Calendar reminder creation does not imply a follow-up was sent;
- legacy tracker records remain backward compatible.

See `docs/AGENTIC_APPLICATION_WORKFLOW.md`.

## Phase 4 — Confidence-aware model routing

Status: **routing implementation complete; adaptive-vs-single empirical benchmark pending**.

The routing principle is to use the smallest configured tier that satisfies a task contract, then escalate only when deterministic quality signals justify it.

```text
Profile extraction ─────────────► economy
Normal structured extraction ───► economy
Complex/long job extraction ────► standard
Grounded matching ───────────────► standard
Agent/tool reasoning ────────────► standard
quality-contract failure ────────► strong repair
```

Implemented engineering controls:

- `adaptive` and backward-compatible `single` routing modes;
- provider-specific economy, standard and strong model tiers;
- deterministic long-offer routing without an extra classifier call;
- strong-tier escalation after claim/evidence validation failure;
- strong-tier escalation after memory-selection validation failure;
- provider fallback preserved independently of task routing;
- tier/model deduplication when two logical tiers use the same physical model;
- route tier, route reason and escalation telemetry;
- token-based cost estimation only when a versioned/configurable pricing catalog is supplied;
- no hard-coded provider prices;
- AI Evaluation UI exposes routing, escalation, latency, tokens, cost coverage and estimated cost;
- adaptive-vs-single report comparator verifies dataset/prompt/protocol identity before comparing results.

The system does **not** trust model self-reported confidence. Escalation is tied to deterministic validation failures.

Remaining acceptance criterion before making optimization claims:

- run the same versioned labeled benchmark under `adaptive` and `single` modes;
- compare task quality, latency, token usage, explicit-price cost, escalation rate and fallback rate;
- publish only measured deltas and keep recruiter/hiring outcome claims out of scope.

See `docs/CONFIDENCE_AWARE_MODEL_ROUTING.md`.

## Product principle

The premium system should be explainable as:

> An evidence-grounded job application copilot that retrieves verified candidate facts, measures retrieval and grounding quality, routes model capacity by task and deterministic quality signals, orchestrates a stateful application workflow, and keeps Gmail/Calendar actions behind explicit human approval.

The LLM is one component of the system, not the system itself.
