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
4. choose either 5 cases for a smoke test or 50 cases for the complete benchmark;
5. start the workflow.

The workflow:

- verifies that the secret exists without printing it;
- installs the project dependencies;
- validates benchmark integrity;
- runs the selected extraction benchmark;
- publishes aggregate metrics in the Actions run summary;
- uploads the complete JSON report as an artifact retained for 30 days.

The artifact is named using the run number and selected case count, for example:

```text
jobcopilot-benchmark-12-5-cases
```

## Recommended sequence

Run 5 cases first. Review the report and confirm that the model, prompt and output schema behave correctly before launching all 50 cases.
