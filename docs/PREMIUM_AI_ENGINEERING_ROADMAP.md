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

The product now has a dedicated **AI Evaluation** surface that separates two kinds of evidence:

1. **runtime diagnostics** for the current application analysis;
2. **offline synthetic benchmark metrics** produced from versioned labeled evaluation data.

Runtime metrics:

- grounding integrity: factual claim count, grounded claims, unsupported claims and unknown evidence IDs;
- evidence coverage: share of factual email claims linked to retrieved verified memories;
- offer-term evidence coverage: share of explicit offer terms aligned to selected candidate evidence;
- retrieval trace: dense, sparse, RRF and reranker provenance for returned evidence;
- system runtime: successful/failed provider attempts, fallback behavior, total and per-operation latency;
- token usage: input/output/total tokens when the provider exposes usage metadata.

Offline evaluation:

- retrieval: MRR, Recall@1/3/5 and NDCG@1/3/5;
- warm-process retrieval latency: mean, median and P95;
- comparative strategies: dense FAISS vs hybrid FAISS+BM25+RRF vs hybrid+cross-encoder;
- compact aggregate benchmark summary with deltas against the dense baseline;
- extraction and claim-grounding benchmark tooling retained as separate evaluation tracks.

Engineering constraints:

- the evaluation dashboard adds no extra LLM call merely to score a run;
- RRF and cross-encoder scores are treated as ranking signals, never fake probabilities;
- prompts, CV facts, job text, generated content, API keys and OAuth tokens are excluded from telemetry;
- current-run observability remains session-scoped rather than creating a new store of candidate text;
- published benchmark summaries contain aggregate metrics only, not case text or user data;
- synthetic evaluation is labeled as synthetic and is never presented as recruiter-outcome evidence.

Acceptance criteria:

- every published metric is tied to a versioned dataset and configuration;
- benchmark artifacts are reproducible in GitHub Actions;
- measured benchmark numbers are reviewed before being turned into README or CV claims.

## Phase 3 — Stateful application agent with human approval gates

Target workflow:

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
INTERVIEW / REJECTED / OFFER
```

The agent may prepare work autonomously, but consequential external actions remain human-supervised.

Engineering requirements:

- explicit state transitions and persisted application state;
- idempotent Gmail/Calendar actions;
- retries that cannot duplicate an external action;
- confirmation gates before external writes;
- clear audit trail for what the agent proposed, what the user approved and what tool executed;
- safe handling of partial failures and resumed sessions.

## Phase 4 — Confidence-aware model routing

Use the smallest model that satisfies a task's quality requirement, then escalate only when needed.

Example routing policy:

```text
structured extraction ───────► small / low-cost model
simple grounded synthesis ───► standard model
low confidence / ambiguity ──► stronger fallback model
```

Measure:

- quality by task class;
- latency by provider/model;
- cost per successful application analysis;
- escalation/fallback rate;
- quality delta versus a single large-model baseline.

A future pricing layer must use explicit versioned/configurable provider rates rather than hard-coded cost assumptions that silently become stale.

## Product principle

The premium system should be explainable as:

> An evidence-grounded job application copilot that retrieves verified candidate facts, measures retrieval and grounding quality, orchestrates a stateful application workflow, and keeps Gmail/Calendar actions behind explicit human approval.

The LLM is one component of the system, not the system itself.
