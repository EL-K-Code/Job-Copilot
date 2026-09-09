# JobCopilot Premium AI Engineering Roadmap

JobCopilot is intentionally evolving from a prompt-driven job assistant into an **evidence-grounded, evaluated, human-supervised agentic system**. The goal is not to imitate a general chat product. The goal is to make the engineering choices around retrieval, grounding, orchestration, evaluation and external actions explicit and measurable.

## Phase 1 — Hybrid evidence retrieval + reranking

Status: in implementation.

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

Engineering requirements:

- keep every retrieval path tenant-scoped;
- preserve stable memory IDs and evidence provenance;
- expose dense rank/distance, sparse rank/score, RRF rank/score and reranker score;
- fail safely to deterministic fused retrieval if the reranker is unavailable;
- keep dense FAISS available as a benchmark baseline;
- compare dense, hybrid and hybrid+reranker on the same labeled retrieval cases;
- claim quality improvements only when the benchmark demonstrates them.

Primary metrics: MRR, Recall@1/3/5, NDCG@1/3/5, retrieval latency.

## Phase 2 — Evaluation and observability layer

Build one evaluation surface for both offline experiments and production traces.

Target metrics:

- retrieval: Recall@K, MRR, NDCG;
- grounding: supported-claim rate, unsupported claims, evidence coverage;
- structured generation: schema-valid output rate and repair/fallback rate;
- system: end-to-end latency, provider/model latency, token usage, estimated cost and failures;
- comparative experiments: model/pipeline configuration versus quality, latency and cost.

Acceptance criteria:

- every published metric is tied to a versioned dataset and configuration;
- synthetic evaluation is clearly labeled as synthetic and is never presented as recruiter outcome evidence;
- benchmark artifacts are reproducible in CI or a documented workflow.

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

## Product principle

The premium system should be explainable as:

> An evidence-grounded job application copilot that retrieves verified candidate facts, measures retrieval and grounding quality, orchestrates a stateful application workflow, and keeps Gmail/Calendar actions behind explicit human approval.

The LLM is one component of the system, not the system itself.
