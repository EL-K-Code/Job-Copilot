# Evaluation

JobCopilot is evaluated as a system rather than through a single successful demo.

## Benchmark V1

`benchmark_manifest.v1.json` freezes the first public benchmark release.

### Extraction corpus

`job_offers.v1.jsonl` contains 50 synthetic, human-authored job offers with expected structured fields:

- 25 English and 25 French offers;
- 15 easy, 18 medium and 17 hard cases;
- LLM agents, NLP/IR, MLOps, data science, data engineering, research, computer vision and ambiguous postings;
- internships, apprenticeships, permanent roles, fixed-term roles, PhD positions, consulting missions and missing-field cases.

Run a low-cost smoke evaluation first:

```bash
python scripts/evaluate_job_extraction.py --limit 5
```

Run the frozen 50-case benchmark with:

```bash
python scripts/evaluate_job_extraction.py
```

This requires a configured Anthropic API key. The report records the model, benchmark version, dataset hash, prompt hash and timestamp. It reports aggregate performance and slices by language, category and difficulty.

### Retrieval benchmark

`retrieval_cases.v1.jsonl` contains 20 relevance-judgment queries against the public synthetic candidate memory.

Run:

```bash
python scripts/evaluate_retrieval.py
```

Reported metrics:

- Recall@1, Recall@3 and Recall@5;
- mean reciprocal rank;
- NDCG@1, NDCG@3 and NDCG@5.

The runner uses local sentence embeddings and does not require an LLM API call, but the embedding model may be downloaded on first use.

### Human grounding review

Prepare generated emails for human claim-level review:

```bash
python scripts/prepare_grounding_review.py --limit 10
```

The generated JSONL file contains the email and retrieved memories. A reviewer must split the email into factual candidate claims and label each claim:

- `supported`;
- `unsupported`;
- `ambiguous`.

After annotation, summarize the unsupported-claim rate with:

```bash
python scripts/summarize_grounding_annotations.py \
  --annotations evaluation/results/grounding_review.jsonl
```

`grounding_annotations.example.jsonl` demonstrates the expected completed format only. It is not a JobCopilot performance result.

## Extraction metrics

- normalized exact accuracy for company, role, location, contract type and start date;
- set precision, recall and F1 for list-valued fields;
- macro-average list F1;
- case-level predictions retained for error analysis.

## Reproducibility

Every generated report is written under `evaluation/results/`, which is ignored by Git because model outputs may contain local candidate data.

The benchmark code validates:

- exactly 50 unique extraction cases;
- manifest distributions;
- required annotation fields;
- 20 unique retrieval cases;
- retrieval judgments referencing valid memory IDs.

See [`ANNOTATION_GUIDE.md`](ANNOTATION_GUIDE.md) for the complete labeling protocol.

## Interpretation boundary

Version 1 uses synthetic offers and a single annotator. Results must not be presented as production accuracy, external validity or real-world generalization. A stronger release requires real public offers or licensed data, two independent annotators, adjudication and an agreement statistic.
