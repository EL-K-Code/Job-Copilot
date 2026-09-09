# JobCopilot AI Evaluation & Observability

JobCopilot treats evaluation as a product feature, not as a post-hoc demo score. The goal is to answer three separate questions without conflating them:

1. **Did retrieval surface the right verified profile evidence?**
2. **Did generated candidate claims remain linked to known evidence?**
3. **How did the LLM system behave at runtime?**

None of these metrics is presented as a recruiter-response or hiring-outcome probability.

## 1. Runtime grounding integrity

Every application analysis exposes deterministic diagnostics computed from the evidence ledger already produced by JobCopilot:

- evidence coverage;
- unsupported factual claim count;
- unknown supporting-memory IDs;
- explicit offer-term evidence coverage;
- uncovered offer-term count.

The checks add no extra LLM call. A grounding-integrity pass means that every factual email claim references retrieved, verified profile-memory IDs and that no unknown memory ID is present.

This is deliberately narrower than a semantic factuality benchmark: it verifies evidence-ledger integrity, not whether a human reviewer would agree with every linguistic interpretation of a source fact.

## 2. Retrieval benchmark

The public benchmark uses the fictional profile in `data/profile_memories.example.json` and 20 labeled retrieval queries in `evaluation/retrieval_cases.v1.jsonl`.

The same cases are evaluated under three strategies:

- **Dense**: `sentence-transformers/all-MiniLM-L6-v2` + FAISS;
- **Hybrid**: dense retrieval + deterministic BM25 + reciprocal-rank fusion;
- **Hybrid + reranker**: hybrid candidate pool + `cross-encoder/ms-marco-MiniLM-L-6-v2`.

Metrics:

- MRR;
- Recall@1 / @3 / @5;
- NDCG@1 / @3 / @5;
- warm-process mean / P50 / P95 retrieval latency.

The committed v2 benchmark snapshot measured:

| Strategy | MRR | Recall@1 | Recall@3 | Recall@5 | NDCG@5 | Mean warm latency |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Dense FAISS | 1.0000 | 0.8250 | 0.9750 | 0.9750 | 0.9766 | 11.1 ms |
| Hybrid | 0.9750 | 0.8000 | 0.9750 | 0.9750 | 0.9613 | 12.0 ms |
| Hybrid + cross-encoder | 0.9750 | 0.7750 | **1.0000** | **1.0000** | 0.9655 | 75.0 ms |

This result is intentionally reported as a trade-off rather than as a blanket improvement: the reranked pipeline recovered all labeled relevant memories by top-5 on this dataset, while dense FAISS retained stronger first-hit/ranking metrics and lower latency.

## 3. Paired uncertainty

Aggregate deltas can look more decisive than a 20-case benchmark supports. The summary pipeline therefore also computes **paired case-level comparisons against dense FAISS**.

For each quality metric and challenger strategy it reports:

- mean paired delta;
- wins / ties / losses;
- fixed-seed 95% paired-bootstrap interval over benchmark cases.

The bootstrap interval quantifies uncertainty over this synthetic benchmark only. It must not be interpreted as uncertainty about recruiter behavior or real hiring outcomes.

## 4. Runtime LLM observability

Application runs expose privacy-safe metadata only:

- provider and model actually used;
- operation name;
- success/error status;
- latency;
- input/output/total tokens when the provider exposes them;
- fallback behavior;
- error class only.

The telemetry layer deliberately excludes:

- prompts;
- CV/profile text;
- job-description text;
- generated application content;
- API keys;
- OAuth tokens;
- raw provider error messages.

## 5. Retrieval provenance

For each evidence item the application can expose, when available:

- dense rank and raw FAISS distance;
- BM25 rank and score;
- reciprocal-rank-fusion rank and score;
- cross-encoder reranker score;
- final rank;
- whether reranking was applied.

Raw retrieval/reranker scores are not converted into fake probabilities. They are ranking signals with different scales and meanings.

## 6. Streamlit AI Evaluation workspace

The private-beta UI contains a dedicated **AI Evaluation** page with two layers:

### Current run

- evidence coverage;
- unsupported claims;
- offer-term evidence coverage;
- uncovered job terms;
- retrieval provenance table;
- dense/sparse recovery counts;
- reranker status;
- LLM calls, latency, token usage and fallback metadata.

### Published synthetic benchmark

- side-by-side dense / hybrid / reranked retrieval metrics;
- latency trade-offs;
- deltas against dense baseline;
- paired-bootstrap uncertainty when present in the published summary.

## 7. Reproducing the retrieval benchmark

```bash
python scripts/evaluate_retrieval.py \
  --dataset evaluation/retrieval_cases.v1.jsonl \
  --output evaluation/results/retrieval_report.json \
  --k 5 \
  --strategies dense hybrid hybrid_rerank

python scripts/summarize_retrieval_report.py \
  --input evaluation/results/retrieval_report.json \
  --output evaluation/results/retrieval_summary.json
```

The GitHub Actions retrieval workflow runs the same comparison on relevant pull requests and publishes both the detailed case-level report and the compact summary as workflow artifacts.

## 8. Interpretation boundary

JobCopilot's evaluation evidence supports engineering claims such as:

- the retrieval subsystem is benchmarked rather than assumed to work;
- hybrid retrieval can recover evidence missed by one retrieval channel;
- reranking introduces measurable quality/latency trade-offs;
- factual candidate claims are auditable against verified memory IDs;
- runtime provider/fallback behavior is observable without storing private content.

It does **not** support claims such as:

- improved recruiter response rate;
- improved interview conversion;
- improved hiring probability;
- superiority on arbitrary external candidate profiles;
- general superiority of hybrid retrieval over dense retrieval.

Those would require a separate real-world evaluation design and additional data.
