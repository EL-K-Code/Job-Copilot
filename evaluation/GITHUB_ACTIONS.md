# Running the Benchmark with GitHub Actions

The manual workflow is defined in `.github/workflows/benchmark.yml`.

## Required repository secret

Create one GitHub Actions repository secret named exactly:

```text
ANTHROPIC_API_KEY
```

Do not place the key in source code, workflow inputs, commit messages, issues, pull requests or logs.

## Add the secret

In the GitHub repository:

1. open **Settings**;
2. open **Secrets and variables**;
3. choose **Actions**;
4. select **New repository secret**;
5. enter `ANTHROPIC_API_KEY` as the name;
6. paste the Anthropic API key as the value and save it.

## Run the workflow

1. open the repository's **Actions** tab;
2. choose **JobCopilot Benchmark**;
3. select **Run workflow**;
4. choose either `5` or `50`;
5. start the workflow.

The options mean:

- `5`: run the dedicated bilingual stratified smoke suite, covering five categories and easy, medium and hard cases;
- `50`: run the full synthetic Benchmark V1 dataset.

The five-case option does not evaluate the first five rows of the full dataset.

The workflow:

- verifies that the secret exists without printing it;
- installs the project dependencies;
- validates both benchmark datasets;
- runs the selected extraction suite;
- publishes protocol 1.2 metrics in the Actions run summary;
- uploads the complete JSON report as an artifact retained for 30 days.

## Metrics shown in the summary

- normalized scalar accuracy;
- strict scalar accuracy;
- closed-label list F1 for skills, tools and domains;
- exact mission-summary F1 as a diagnostic;
- selected dataset and evaluation-protocol version.

Contract type is scored through a broad normalized category for the primary scalar metric, while strict wording remains visible separately. Mission summaries are excluded from closed-label macro F1 because faithful paraphrases may differ lexically. `key_highlights_for_candidate` is excluded because it is a generated recommendation field.

The artifact is named using the run number and selected case count, for example:

```text
jobcopilot-benchmark-12-5-cases
```

## Recommended sequence

Run the five-case stratified suite first. Review contract behavior, French extraction, strict-versus-normalized differences and mission-summary diagnostics before launching all 50 cases.
