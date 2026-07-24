# Structured Extraction Benchmark V1 — Published Results

## Run identity

| Item | Value |
| --- | --- |
| Dataset | `evaluation/job_offers.v1.jsonl` |
| Dataset version | `1.0.0` |
| Evaluation protocol | `1.2.0` |
| Cases | 50 synthetic English job offers |
| Role families | 10 |
| Model | `claude-sonnet-4-6` |
| Generated at | `2026-07-24T13:13:29.628890+00:00` |
| Dataset SHA-256 | `b14c2602d3a06ac5aa80f9d2580f2205270747ed95566aa6140d5fe477da7df5` |
| Prompt SHA-256 | `895ee4797dcf0423298f058f12927f71a2e50e0c7a69e589d0ff1b71ca95d7c2` |

## Aggregate results

| Metric | Score |
| --- | ---: |
| Normalized scalar accuracy | **1.0000** |
| Strict scalar accuracy | **1.0000** |
| Closed-label list macro F1 | **0.9980** |
| Mission-summary exact F1 | **1.0000** |

### Scalar accuracy by field

| Field | Normalized | Strict |
| --- | ---: | ---: |
| Company | 1.0000 | 1.0000 |
| Role | 1.0000 | 1.0000 |
| Location | 1.0000 | 1.0000 |
| Contract type | 1.0000 | 1.0000 |
| Start date | 1.0000 | 1.0000 |

### Closed-label list F1 by field

| Field | F1 |
| --- | ---: |
| Required skills | 1.0000 |
| Preferred skills | 1.0000 |
| Tools and stack | 1.0000 |
| Domain focus | 0.9920 |

### Results by role family

Each role family contains five cases.

| Role family | Normalized scalar accuracy | Strict scalar accuracy | Closed-label list F1 | Mission-summary exact F1 |
| --- | ---: | ---: | ---: | ---: |
| Analytics | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| Cloud AI | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| Computer Vision | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| Data Engineering | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| Information Retrieval | 1.0000 | 1.0000 | 0.9900 | 1.0000 |
| LLM Applications | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| MLOps | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| Machine Learning | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| Research | 1.0000 | 1.0000 | 0.9900 | 1.0000 |
| Responsible AI | 1.0000 | 1.0000 | 1.0000 | 1.0000 |

## Case-level deviations

Forty-eight of the fifty cases received perfect scores under all protocol 1.2 metrics. The two remaining deviations affected only `domain_focus`.

### `offer_030` — Information Retrieval

Expected:

```json
["information retrieval", "semantic search"]
```

Predicted:

```json
["RAG", "Information retrieval", "Semantic search"]
```

The model recovered every gold label and added `RAG`, which is supported by the role title `RAG Retrieval Engineer` but is absent from the narrower explicit `Domain focus` annotation.

### `offer_049` — Research

Expected:

```json
["applied research", "reproducibility"]
```

Predicted:

```json
["NLP", "Applied research", "Reproducibility"]
```

The model recovered every gold label and added `NLP`, which is supported by the title `NLP Research Intern` but is absent from the narrower explicit `Domain focus` annotation.

For both cases, domain-focus precision was `0.6667`, recall was `1.0000`, and F1 was `0.8000`.

## Interpretation

The run demonstrates highly reliable extraction on the frozen synthetic suite and is suitable for regression testing and controlled engineering comparisons.

It does **not** establish 99.8% performance on the open job market. The full V1 suite is:

- synthetic and manually authored;
- English-only;
- strongly templated with explicit headings;
- composed of five variants for each of ten role families;
- less diverse than real advertisements from multiple companies and platforms.

The two deviations also expose an annotation-policy question: should `domain_focus` contain every domain supported anywhere in the offer, or only labels stated in an explicit domain section? Benchmark V2 must define this boundary before annotation.

## Reproduction

Validate the frozen datasets:

```bash
python scripts/validate_benchmark.py
```

Run the complete extraction benchmark:

```bash
python scripts/evaluate_job_extraction.py \
  --dataset evaluation/job_offers.v1.jsonl \
  --benchmark-version 1.0.0
```

The complete report records the model name, dataset hash, prompt hash, protocol version, aggregate metrics, slices and case-level predictions.

## Responsible result statement

> On a frozen synthetic benchmark of 50 English job offers across 10 role families, Claude Sonnet 4.6 achieved 100% normalized and strict scalar accuracy, 99.8% macro F1 on closed-label list extraction, and 100% exact F1 on mission summaries. The two remaining deviations were additional domain labels supported by role titles but absent from the narrower gold annotations. The suite is intended for regression testing, not as evidence of production-level generalization.
