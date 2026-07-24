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

The options now mean:

- `5`: run the dedicated bilingual stratified smoke suite, covering five categories and easy, medium and hard cases;
- `50`: run the full synthetic Benchmark V1 dataset.

The five-case option no longer evaluates the first five rows of the full dataset.

The workflow:

- verifies that the secret exists without printing it;
- installs the project dependencies;
- validates both benchmark datasets;
- runs the selected extraction suite;
- publishes aggregate metrics in the Actions run summary;
- uploads the complete JSON report as an artifact retained for 30 days.

The summary explicitly reports the selected dataset and evaluation-protocol version. Macro list F1 covers only direct extraction fields; `key_highlights_for_candidate` is excluded because it is a generated recommendation field.

The artifact is named using the run number and selected case count, for example:

```text
jobcopilot-benchmark-12-5-cases
```

## Recommended sequence

Run the new five-case stratified suite first. Review the contract-type behavior, French extraction and field-level metrics before launching all 50 cases.
