# Running Evaluations with GitHub Actions

JobCopilot keeps expensive or model-dependent evaluations manual. None of the workflows described here runs on pushes, pull requests or schedules.

## Required repository secret

The extraction benchmark and generated-email grounding preparation require one GitHub Actions repository secret named exactly:

```text
ANTHROPIC_API_KEY
```

The retrieval benchmark does not use Anthropic and requires no API secret.

Do not place the key in source code, workflow inputs, commit messages, issues, pull requests or logs.

## Add the secret

In the GitHub repository:

1. open **Settings**;
2. open **Secrets and variables**;
3. choose **Actions**;
4. select **New repository secret**;
5. enter `ANTHROPIC_API_KEY` as the name;
6. paste the Anthropic API key as the value and save it.

## 1. Structured extraction

Workflow: **JobCopilot Benchmark**  
File: `.github/workflows/benchmark.yml`

1. open the repository's **Actions** tab;
2. choose **JobCopilot Benchmark**;
3. select **Run workflow**;
4. choose either `5` or `50`;
5. start the workflow.

The options mean:

- `5`: run the bilingual stratified smoke suite;
- `50`: run the full synthetic Benchmark V1 dataset.

The workflow validates the datasets, runs extraction, publishes protocol 1.2 metrics and uploads the complete JSON report for 30 days.

Metrics shown:

- normalized scalar accuracy;
- strict scalar accuracy;
- closed-label list F1 for skills, tools and domains;
- exact mission-summary F1 as a lexical diagnostic;
- selected dataset and evaluation-protocol version.

Contract type is scored through a broad normalized category for the primary scalar metric, while strict wording remains visible separately. Mission summaries are excluded from closed-label macro F1 because faithful paraphrases may differ lexically. `key_highlights_for_candidate` is excluded because it is a generated recommendation field.

Example artifact:

```text
jobcopilot-benchmark-12-50-cases
```

Published V1 results are documented in [`EXTRACTION_RESULTS_V1.md`](EXTRACTION_RESULTS_V1.md), with a machine-readable compact record under [`published/extraction_v1_summary.json`](published/extraction_v1_summary.json).

## 2. Profile-memory retrieval

Workflow: **JobCopilot Retrieval Benchmark**  
File: `.github/workflows/retrieval-benchmark.yml`

This workflow:

- uses the fictional public profile only;
- builds the FAISS index from auditable JSON;
- downloads or restores the `sentence-transformers/all-MiniLM-L6-v2` embedding model;
- evaluates all 20 retrieval cases;
- reports MRR, Recall@1/3/5 and NDCG@1/3/5;
- uploads the ranked case-level JSON report for 30 days.

It requires no Anthropic key and does not access private candidate data.

Example artifact:

```text
jobcopilot-retrieval-3
```

## 3. Generated-email grounding review preparation

Workflow: **JobCopilot Grounding Review Preparation**  
File: `.github/workflows/grounding-review.yml`

Choose `5`, `10` or `50` generated emails. The workflow uses the fictional public profile, runs the complete JobCopilot pipeline and creates a JSONL annotation template.

Small runs are selected through deterministic category-stratified sampling rather than taking the first dataset rows. This prevents a five-case review from containing five near-duplicate offers from one role family. The 50-case option still evaluates the complete frozen dataset.

For each offer, the pipeline:

1. retrieves profile memories with FAISS;
2. scores the retrieved memories against explicit required skills, tools, domains, role terms and missions;
3. asks the LLM to select only one to three retrieved memory IDs;
4. constructs every candidate claim deterministically from the selected memory text;
5. varies only safe non-factual opening and closing templates;
6. exports relevance scores, aligned offer terms, selected memory IDs and the complete claim ledger.

The output is deliberately **not scored automatically**. A human reviewer must:

1. verify every factual candidate claim against its cited memory;
2. label every claim `supported`, `unsupported` or `ambiguous`;
3. confirm that no candidate claim exists outside the ledger;
4. assess whether the selected evidence is genuinely specific to the role rather than merely generic;
5. reference only retrieved memory IDs as evidence.

After annotation, run:

```bash
python scripts/summarize_email_grounding_review.py \
  --annotations evaluation/results/email_grounding_review.jsonl
```

Example artifact:

```text
jobcopilot-grounding-review-5-10-cases
```

## Recommended sequence

1. run the five-case extraction smoke suite;
2. run the full 50-case extraction benchmark;
3. run the 20-case retrieval benchmark;
4. prepare five stratified generated emails for grounding and personalization review;
5. audit support, ledger coverage and role-specific evidence selection;
6. expand to ten role families before considering a full 50-email review;
7. keep Benchmark V2 work separate from frozen V1 results.
