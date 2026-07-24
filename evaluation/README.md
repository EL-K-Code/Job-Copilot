# JobCopilot Evaluation

JobCopilot is evaluated as a system, not only demonstrated through a successful prompt.

## Evaluation protocol 1.2

Protocol 1.2 makes four distinct measurements explicit instead of collapsing them into one score:

1. normalized scalar accuracy, where `contract_type` is compared through a broad multilingual category;
2. strict scalar accuracy, which preserves exact normalized wording as a diagnostic;
3. closed-label list F1 for skills, tools and domains;
4. exact mission-summary F1 as a separate lexical diagnostic because valid paraphrases may differ.

`key_highlights_for_candidate` remains visible for review but is excluded from extraction F1 because it is a generated recommendation field.

The evaluator also normalizes documented acronym and expanded-form equivalents such as NLP / natural language processing and RAG / retrieval-augmented generation. Semantic modifiers remain distinct: `LLM evaluation` is different from `LLM deployment`, and `responsible AI` is different from `agentic AI`.

## Published extraction result

The controlled 50-offer V1 run is published in:

- [`EXTRACTION_RESULTS_V1.md`](EXTRACTION_RESULTS_V1.md): human-readable methodology, results, deviations and limitations;
- [`published/extraction_v1_summary.json`](published/extraction_v1_summary.json): compact machine-readable record with hashes and aggregate metrics.

Headline result on the frozen synthetic English suite:

| Metric | Score |
| --- | ---: |
| Normalized scalar accuracy | 1.0000 |
| Strict scalar accuracy | 1.0000 |
| Closed-label list macro F1 | 0.9980 |
| Mission-summary exact F1 | 1.0000 |

These scores are regression-test evidence on a strongly templated synthetic suite, not production-level job-market accuracy.

## Available suites

### Stratified smoke suite

`job_offers.smoke.v1.jsonl` contains five synthetic cases designed for low-cost validation before a complete run:

- English and French;
- five distinct role categories;
- easy, medium and hard cases;
- missing contract and start-date fields;
- a case where an internship-like word appears only in the job title;
- an offer whose final location overrides an earlier header location.

Run locally:

```bash
python scripts/evaluate_job_extraction.py \
  --dataset evaluation/job_offers.smoke.v1.jsonl \
  --benchmark-version smoke-1.0.0
```

### Full Benchmark V1

`job_offers.v1.jsonl` contains 50 synthetic English offers across 10 role families. It is useful for regression testing but is not yet a bilingual or externally representative benchmark.

Run:

```bash
python scripts/evaluate_job_extraction.py \
  --dataset evaluation/job_offers.v1.jsonl \
  --benchmark-version 1.0.0
```

Both extraction runs require a configured Anthropic API key.

## Extraction metrics

### Scalar fields

- company;
- role;
- location;
- contract type;
- start date.

For `contract_type`, the report contains two views:

- `scalar_fields.contract_type`: broad normalized category match, supporting multilingual equivalents such as `CDI` / `Permanent`, `Stage` / `Internship`, and `Full-time permanent role` / `Full-time`;
- `strict_scalar_fields.contract_type`: exact normalized wording match, preserving omitted qualifiers as a visible diagnostic.

The aggregate report therefore includes both `mean_scalar_accuracy` and `mean_strict_scalar_accuracy`.

### Closed-label list fields

The macro list F1 covers only fields that behave like label sets:

- required skills;
- preferred skills;
- tools and stack;
- domain focus.

These fields are reported under `list_fields`, with aggregate metric `mean_macro_label_list_f1`. The backward-compatible key `mean_macro_list_f1` carries the same value.

### Mission summaries

`missions_summary` remains a direct extraction target, but a short faithful paraphrase may not match the reference text exactly. It is therefore reported separately under `summary_fields` with `mean_summary_exact_f1`.

This is an exact normalized lexical diagnostic, not a semantic-equivalence claim. A stronger evaluation should add blinded human review or a separately validated semantic metric.

### Generated recommendations

`key_highlights_for_candidate` remains in each case report under `unscored_fields`. It requires human or semantic evaluation because the schema asks for actionable recommendations rather than copied labels.

## Report contents

Reported outputs include:

- normalized and strict scalar accuracy;
- closed-label macro F1;
- exact mission-summary F1 as a diagnostic;
- accuracy or F1 by individual field;
- slices by language, category and difficulty when metadata is available;
- case-level predictions and expected values;
- model name, dataset version, evaluation-protocol version, dataset hash, prompt hash and timestamp.

## Contract-type extraction rule

The extraction prompt treats the role title and contract type as separate evidence. Terms such as `Intern`, `Apprentice`, `Fellow`, `Consultant` or `Freelance` inside a title must not determine `contract_type`. The field is populated only when the offer explicitly states the employment or contract type; otherwise it must be `Unknown`.

## Profile-memory retrieval evaluation

`retrieval_cases.v1.jsonl` contains 20 profile-memory relevance judgments.

Run locally:

```bash
python scripts/evaluate_retrieval.py \
  --dataset evaluation/retrieval_cases.v1.jsonl \
  --output evaluation/results/retrieval_report.json
```

Or run the manual **JobCopilot Retrieval Benchmark** GitHub Actions workflow. It uses the fictional public profile, requires no Anthropic secret and uploads the full ranked report.

Reported metrics:

- Recall@1, Recall@3 and Recall@5;
- MRR;
- NDCG@1, NDCG@3 and NDCG@5;
- ranked memory IDs for case-level analysis.

The first run may download the configured sentence-transformer model.

## Static grounding-label benchmark

`grounding_cases.v1.jsonl` evaluates whether a model or reviewer can classify isolated candidate claims against specified evidence.

A prediction file contains one object per case:

```json
{"id": "ground_001", "label": "supported"}
```

Score it with:

```bash
python scripts/evaluate_grounding.py \
  --predictions evaluation/results/grounding_predictions.jsonl
```

This task measures grounding-label classification. It does not by itself measure the unsupported-claim rate of emails generated by JobCopilot.

## Generated-email grounding review

Generate JobCopilot outputs and prepare them for human review:

```bash
python scripts/prepare_email_grounding_review.py --limit 10
```

The manual **JobCopilot Grounding Review Preparation** workflow can prepare 5, 10 or 50 records using only the fictional public profile.

Reviewers split each email into factual candidate claims and assign:

- `supported`;
- `unsupported`;
- `ambiguous`.

Supported and ambiguous claims must list retrieved memory IDs. Unsupported claims must list no evidence IDs.

After annotation:

```bash
python scripts/summarize_email_grounding_review.py \
  --annotations evaluation/results/email_grounding_review.jsonl
```

The unsupported-claim rate is not produced until human claim segmentation and labeling are complete.

## Benchmark V2

[`BENCHMARK_V2_PLAN.md`](BENCHMARK_V2_PLAN.md) defines the next generalization suite: 100 English and French offers, broader formats, challenge metadata, evidence spans, double annotation, adjudication, cost and latency tracking, and repeated-run stability.

V1 remains frozen for regression testing. V2 results must be reported separately.

## GitHub Actions

See [`GITHUB_ACTIONS.md`](GITHUB_ACTIONS.md) for the three manual workflows:

1. structured extraction;
2. profile-memory retrieval;
3. generated-email grounding review preparation.

## Integrity validation

```bash
python scripts/validate_benchmark.py
```

The validator checks:

- exactly 50 unique full-benchmark offers across at least 10 categories;
- exactly five stratified smoke cases;
- both English and French in the smoke suite;
- five distinct smoke-test categories;
- easy, medium and hard smoke cases;
- required annotation fields;
- valid retrieval and grounding references.

## Interpretation boundary

All current offers are synthetic and manually authored. Results support regression testing and comparative engineering experiments, not production-accuracy or job-market-generalization claims. A stronger release requires licensed or redistributable real-world offers, independent annotators, adjudication and repeated runs across models.
