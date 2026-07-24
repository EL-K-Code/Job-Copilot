<div align="center">

# JobCopilot

### Evidence-grounded, human-supervised agentic AI for job applications

JobCopilot turns a raw job description into a structured and reviewable workflow: offer extraction, semantic profile retrieval, candidate-to-role matching, tailored email drafting, local application tracking and explicitly approved Gmail or Calendar actions.

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-Agent%20Orchestration-1C3C3C)
![Streamlit](https://img.shields.io/badge/Streamlit-Interactive%20UI-FF4B4B?logo=streamlit&logoColor=white)
![CI](https://github.com/EL-K-Code/Job-Copilot/actions/workflows/ci.yml/badge.svg)
![Status](https://img.shields.io/badge/Status-Local%20Engineering%20MVP-2E8B57)

</div>

---

## Why this project exists

Job applications are repetitive and often written from generic summaries rather than verifiable candidate evidence.

JobCopilot explores a safer workflow:

1. extract requirements explicitly stated in an offer;
2. retrieve only relevant candidate memories;
3. separate strengths, gaps and positioning suggestions;
4. draft an email from the retrieved evidence;
5. keep the human in control before external side effects;
6. track the application and prepare a follow-up;
7. measure extraction, retrieval and grounding rather than relying on screenshots alone.

The project is not designed for indiscriminate mass applications. It is a **traceable, local and supervised AI engineering case study**.

---

## Recruiter quick scan

| Capability | Current implementation |
| --- | --- |
| Structured job understanding | Anthropic LLM output validated with Pydantic |
| Candidate memory | Hugging Face embeddings and FAISS retrieval |
| Evidence-aware matching | Explicit strengths, gaps and relevant profile memories |
| Email generation | Structured and editable application draft |
| Deterministic orchestration | Stateless LangGraph pipeline |
| Conversational orchestration | LangGraph tool-calling agent with isolated chat threads |
| Gmail and Calendar | Local Google OAuth with explicit confirmation gates |
| Persistence | Atomic local JSON writes with duplicate checks |
| Evaluation | 50-offer extraction benchmark, 20 retrieval cases and human grounding protocol |
| Delivery | Streamlit UI, Dockerfile and GitHub Actions CI |

---

## System architecture

```mermaid
flowchart LR
    A[Raw job description] --> B[Structured job analysis]
    B --> C[Profile-memory retrieval]
    C --> D[Evidence-aware match]
    D --> E[Editable email draft]
    E --> F{Human review}
    F -->|Approve| G[Save local record]
    F -->|Explicitly confirm| H[Create Gmail draft]
    F -->|Explicitly confirm| I[Create Calendar event]
```

### Deterministic pipeline

```text
analyze_job
    -> retrieve_memory
    -> generate_match
    -> generate_email
```

The deterministic graph is stateless. Separate analyses therefore do not share a workflow checkpoint.

### Tool-calling agent

The conversational agent can:

- run the JobCopilot pipeline;
- preview Gmail and Calendar actions;
- save application records;
- list saved applications.

Gmail and Calendar tools require `confirmed=true`. The agent must show the exact action and request confirmation before the side effect is allowed.

---

## Reliability and safety choices

### Structured outputs

`JobAnalysis`, `MatchInsight`, `EmailDraft` and `ApplicationRecord` are validated with Pydantic. Required text, reminder dates, email subjects and ISO timestamps have explicit validation boundaries.

### Evidence grounding

The matching prompt is restricted to the structured offer and retrieved candidate memories. The email prompt must not convert a suggestion or unsupported skill into a candidate claim.

### External-action approval

The agent cannot create a Gmail draft or Calendar event only because a user mentioned one. It first returns a preview and requires explicit confirmation of the final values.

The dedicated Streamlit buttons represent direct user approval because the editable values are visible before the click.

### Safer FAISS handling

Persisted LangChain FAISS stores include pickle-backed metadata. Deserialization is disabled by default.

JobCopilot rebuilds the in-memory index from auditable JSON and caches it for the process lifetime. Loading a persisted index requires:

```env
ALLOW_TRUSTED_FAISS_DESERIALIZATION=true
```

Enable this only for an index generated locally and kept on a trusted machine.

### Atomic local persistence

Application records are written through a temporary file and atomically replace the target JSON file. Invalid JSON raises an explicit error instead of silently behaving like an empty database.

### Input validation

Before Gmail or Calendar calls, JobCopilot validates:

- email addresses;
- empty bodies and subjects;
- newline-based header injection attempts;
- follow-up date format;
- event start and end ordering.

See [`SECURITY.md`](SECURITY.md) for the complete trust model.

---

## Public demo data and private profile data

The repository ships with:

```text
data/profile_memories.example.json
```

This file contains a fictional candidate profile.

For a personal local profile:

1. copy the example to `data/profile_memories.json`;
2. replace the entries with verified evidence;
3. set:

```env
PROFILE_MEMORIES_FILE=data/profile_memories.json
```

`data/profile_memories.json`, OAuth credentials, tokens and generated application records are ignored by Git.

---

## Benchmark V1

The benchmark is versioned through:

```text
evaluation/benchmark_manifest.v1.json
```

### 1. Structured extraction

`evaluation/job_offers.v1.jsonl` contains **50 synthetic, human-authored offers**:

- 25 English and 25 French;
- 15 easy, 18 medium and 17 hard cases;
- LLM agents, NLP/IR, MLOps, data science, data engineering, research, computer vision and ambiguous postings;
- explicit missing-field and conflicting-context cases.

Run a smoke evaluation:

```bash
python scripts/evaluate_job_extraction.py --limit 5
```

Run the frozen 50-case benchmark:

```bash
python scripts/evaluate_job_extraction.py
```

Reported outputs include:

- normalized exact accuracy for scalar fields;
- precision, recall and F1 for list fields;
- aggregate metrics;
- slices by language, category and difficulty;
- case-level predictions for error analysis;
- model name, dataset hash, prompt hash and timestamp.

### 2. Profile-memory retrieval

`evaluation/retrieval_cases.v1.jsonl` contains **20 graded relevance queries**.

Run:

```bash
python scripts/evaluate_retrieval.py
```

Reported metrics:

- Recall@1, Recall@3 and Recall@5;
- mean reciprocal rank;
- NDCG@1, NDCG@3 and NDCG@5.

### 3. Candidate-claim grounding

Prepare generated emails for human review:

```bash
python scripts/prepare_grounding_review.py --limit 10
```

Reviewers split each email into factual candidate claims and assign:

- `supported`;
- `unsupported`;
- `ambiguous`.

Summarize the review:

```bash
python scripts/summarize_grounding_annotations.py \
  --annotations evaluation/results/grounding_review.jsonl
```

The primary grounding metric is the **unsupported claim rate**. Ambiguous claims are reported separately.

See [`evaluation/README.md`](evaluation/README.md) and [`evaluation/ANNOTATION_GUIDE.md`](evaluation/ANNOTATION_GUIDE.md) for the full protocol.

> Benchmark V1 uses synthetic offers and one annotator. It does not establish production accuracy or real-world generalization.

---

## Repository structure

```text
app/
  agent_graph.py
  agent_tools.py
  config.py
  evaluation.py
  graph.py
  memory.py
  prompts.py
  schemas.py
  services/
  tools/
  ui/

data/
  profile_memories.example.json

evaluation/
  ANNOTATION_GUIDE.md
  README.md
  benchmark_manifest.v1.json
  grounding_annotations.example.jsonl
  job_offers.v1.jsonl
  retrieval_cases.v1.jsonl

scripts/
  evaluate_job_extraction.py
  evaluate_retrieval.py
  prepare_grounding_review.py
  summarize_grounding_annotations.py

tests/
.github/workflows/ci.yml
Dockerfile
SECURITY.md
```

---

## Local setup

### 1. Create an environment

```bash
git clone https://github.com/EL-K-Code/Job-Copilot.git
cd Job-Copilot
python -m venv .venv
```

Linux or macOS:

```bash
source .venv/bin/activate
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

For tests:

```bash
pip install -r requirements-dev.txt
```

### 3. Configure local variables

```bash
cp .env.example .env
```

At minimum:

```env
ANTHROPIC_API_KEY=your_local_key
ANTHROPIC_MODEL=your_supported_model
```

Never commit the resulting `.env` file.

### 4. Run the application

```bash
streamlit run app/ui/streamlit_app.py --server.address 127.0.0.1 --server.port 8501
```

---

## Google OAuth setup

To enable Gmail and Calendar locally:

1. create a Google Cloud project;
2. enable Gmail API and Google Calendar API;
3. configure the OAuth consent screen;
4. create a Desktop OAuth client;
5. save the downloaded file as `credentials.json`;
6. run:

```bash
python -m app.bootstrap_gmail_auth
```

The OAuth file and generated tokens are ignored by Git.

---

## Docker

```bash
docker build -t jobcopilot .
```

```bash
docker run --rm -p 8501:8501 \
  --env-file .env \
  -v "$(pwd)/data:/app/data" \
  -v "$(pwd)/tokens:/app/tokens" \
  -v "$(pwd)/credentials.json:/app/credentials.json:ro" \
  jobcopilot
```

Do not bake credentials, OAuth tokens or personal profile files into the image.

---

## Tests and CI

Run locally:

```bash
python -m compileall -q app tests scripts
pytest -q
```

GitHub Actions runs syntax and unit-test checks for pull requests and pushes to `main`.

The test suite covers:

- duplicate detection and atomic JSON persistence;
- corrupted-store behavior;
- agent confirmation gates;
- Gmail and Calendar validation;
- schema validation;
- extraction metrics;
- retrieval metrics;
- grounding metrics;
- benchmark size, distributions and reference integrity.

---

## Current boundaries

JobCopilot remains a **local engineering MVP**, not a production service.

Known limitations:

- JSON persistence is not transactional across concurrent processes;
- the agent checkpointer is in memory;
- there is no authentication or multi-user authorization;
- no public hosted deployment is configured;
- Benchmark V1 is synthetic and single-annotator;
- retrieval has no learned reranker or calibrated relevance threshold;
- Gmail and Calendar rely on local desktop OAuth;
- observability does not yet provide full traces, cost accounting or redacted audit logs.

---

## Roadmap

1. run and publish the 50-case extraction benchmark with controlled model settings;
2. complete claim-level human review across the frozen benchmark;
3. add a second independent annotator and disagreement adjudication;
4. add real public offers or licensed data without reproducing copyrighted postings;
5. migrate persistence to SQLite with migrations;
6. introduce structured tracing and redacted audit logs;
7. add retrieval reranking and relevance thresholds;
8. publish screenshots and a short synthetic-data demonstration;
9. deploy only after authentication, secret management and per-user isolation.

---

## Author

**Komla Alex LABOU**  
Applied AI and Machine Learning Engineer — Research-Oriented

- GitHub: [EL-K-Code](https://github.com/EL-K-Code)
- LinkedIn: [komla-alex-labou](https://www.linkedin.com/in/komla-alex-labou/)
