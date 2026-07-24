# JobCopilot Evaluation

JobCopilot is evaluated as a system, not only demonstrated through a successful prompt.

## Benchmark V1

Benchmark V1 is a frozen, synthetic and human-authored evaluation suite. It is designed to make the repository measurable while avoiding redistribution of copyrighted job advertisements or private candidate data.

It contains:

- `job_offers.v1.jsonl`: 50 annotated offers across 10 role families;
- `retrieval_cases.v1.jsonl`: 20 profile-memory relevance judgments;
- `grounding_cases.v1.jsonl`: 20 candidate-claim annotations labeled `supported`, `unsupported` or `ambiguous`.

The 10 offer families are LLM applications, machine learning, data engineering, MLOps, computer vision, information retrieval, responsible AI, analytics, cloud AI and applied research.

## Integrity validation

The CI validates that:

- the extraction dataset contains exactly 50 unique offers;
- all expected schema fields are present;
- at least 10 role categories are represented;
- retrieval and grounding cases reference valid public-demo memory IDs;
- all grounding labels are valid and all three classes are represented.

Run locally:

```bash
python scripts/validate_benchmark.py
```

## 1. Structured extraction evaluation

```bash
python scripts/evaluate_job_extraction.py \
  --dataset evaluation/job_offers.v1.jsonl \
  --output evaluation/results/job_extraction_report.json
```

This requires a configured Anthropic API key.

Reported metrics:

- normalized exact accuracy for company, role, location, contract type and start date;
- set precision, recall and F1 for list-valued fields;
- macro-average list F1;
- per-case predictions retained for error analysis.

## 2. Profile-memory retrieval evaluation

```bash
python scripts/evaluate_retrieval.py \
  --dataset evaluation/retrieval_cases.v1.jsonl \
  --output evaluation/results/retrieval_report.json
```

Reported metrics:

- Recall@1, Recall@3 and Recall@5;
- MRR;
- NDCG@1, NDCG@3 and NDCG@5;
- ranked memory IDs for case-level analysis.

The first run may download the configured sentence-transformer model.

## 3. Candidate-claim grounding evaluation

The gold file contains claims and evidence references. A model or reviewer must produce a JSONL prediction file with one object per case:

```json
{"id": "ground_001", "label": "supported"}
```

Score it with:

```bash
python scripts/evaluate_grounding.py \
  --predictions evaluation/results/grounding_predictions.jsonl
```

Reported metrics:

- accuracy;
- macro F1;
- precision, recall and F1 by label;
- gold label distribution.

## Versioning and reporting rules

Every empirical report should record:

- dataset version;
- model name;
- prompt version or commit SHA;
- run timestamp;
- number of cases successfully processed;
- failed or retried API calls;
- aggregate metrics and per-case outputs.

## Interpretation boundary

Benchmark V1 is synthetic and manually authored by the project owner. It is useful for regression testing, comparative experiments and portfolio evidence, but it is **not production-accuracy evidence** and must not be described as representative of the full job market.

A stronger V2 should add independently annotated real-world offers whose licensing permits redistribution, inter-annotator agreement, multilingual cases, adversarially incomplete offers and repeated runs across several models.
