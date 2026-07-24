# Evaluation

JobCopilot should be evaluated as a system, not only demonstrated through a successful prompt.

## Current starter benchmark

`job_offers.sample.jsonl` contains synthetic job offers with human-authored expected fields. It is intentionally small and is provided to validate the evaluation pipeline, not to support broad performance claims.

Run the extraction evaluation with:

```bash
python scripts/evaluate_job_extraction.py
```

The command requires a configured Anthropic API key and writes a detailed JSON report to `evaluation/results/job_extraction_report.json` by default.

## Reported extraction metrics

- exact normalized accuracy for company, role, location, contract type and start date;
- set precision, recall and F1 for list-valued fields;
- macro-average F1 across the evaluated list fields;
- predictions and expected values retained for error analysis.

## Next benchmark milestones

1. Expand to at least 50 diverse offers across internship, junior, research and engineering roles.
2. Annotate each offer independently and resolve disagreements before evaluation.
3. Add retrieval relevance judgments for profile memories and report Recall@k and NDCG@k.
4. Label every generated candidate claim as supported, unsupported or ambiguous.
5. Measure external-tool success, duplicate-action rate, latency and model cost.
6. Store the model name, prompt version, dataset version and run timestamp with every report.

## Interpretation boundary

The synthetic starter cases are a test fixture. Results on them must not be described as production accuracy or generalization evidence. A credible public result requires a larger frozen dataset, documented annotation rules and repeated runs when model outputs are stochastic.
