# Evaluation

JobCopilot should be evaluated as a system, not only demonstrated through a successful prompt.

## Current benchmark

`job_offers.sample.jsonl` contains **10 synthetic job offers with human-authored reference annotations**. The cases cover:

- agentic AI and RAG;
- MLOps and model serving;
- NLP research and information retrieval;
- computer vision;
- energy forecasting;
- responsible AI;
- cloud data engineering;
- recommender systems;
- LLM and agent evaluation;
- multimodal AI research.

The current coverage includes six medium-difficulty and four hard-difficulty cases. All cases are English-language synthetic fixtures. They validate the benchmark and evaluation infrastructure, but they do not support claims about real-world generalization.

## Annotation contract

Each JSONL line contains:

```json
{
  "id": "lowercase-kebab-case-id",
  "metadata": {
    "source_type": "synthetic",
    "language": "en",
    "track": "llm_evaluation",
    "difficulty": "hard"
  },
  "job_text": "Full benchmark offer text...",
  "expected": {
    "company": "...",
    "role": "...",
    "location": "...",
    "contract_type": "...",
    "start_date": "...",
    "missions_summary": [],
    "required_skills": [],
    "preferred_skills": [],
    "tools_and_stack": [],
    "profile_summary": "...",
    "domain_focus": [],
    "key_highlights_for_candidate": []
  }
}
```

Identifiers must be unique. Every `JobAnalysis` field must be annotated, list annotations must not contain case-insensitive duplicates, and metadata must include source type, language, track and difficulty.

## Validate the dataset

Run the deterministic validator before any model call:

```bash
python scripts/validate_benchmark.py
```

The command checks JSONL syntax, required fields, Pydantic compatibility, unique identifiers, annotation duplicates and metadata values. It also prints a coverage summary. GitHub Actions runs this validation on every pull request and push to `main`.

## Run extraction evaluation

```bash
python scripts/evaluate_job_extraction.py
```

The command requires a configured Anthropic API key and writes a detailed JSON report to:

```text
evaluation/results/job_extraction_report.json
```

Each report records the model name, UTC timestamp, dataset coverage, per-case predictions, reference annotations and metrics.

## Reported extraction metrics

- exact normalized accuracy for company, role, location, contract type and start date;
- set precision, recall and F1 for list-valued fields;
- macro-average F1 across the evaluated list fields;
- predictions and expected values retained for error analysis.

Exact set matching is intentionally strict. Synonyms such as `retrieval-augmented generation` and `RAG` are treated as different annotations unless normalization is expanded in a documented future protocol.

## Next benchmark milestones

1. Expand from 10 to 25 cases with more ambiguous wording, missing fields and mixed contract formats.
2. Reach at least 50 frozen cases, including rights-safe paraphrases of real offers with source provenance.
3. Annotate a subset independently and report inter-annotator agreement before resolving disagreements.
4. Add retrieval relevance judgments and report Recall@k and NDCG@k.
5. Label generated candidate claims as supported, unsupported or ambiguous.
6. Measure tool success, duplicate-action rate, latency and estimated model cost.
7. Version the dataset and prompts so benchmark results remain comparable over time.

## Interpretation boundary

The ten synthetic cases are a structured test fixture. Results must not be described as production accuracy, hiring effectiveness or evidence of broad generalization. A credible public result requires a larger frozen dataset, documented annotation guidelines, error analysis and repeated runs when model behavior is stochastic.
