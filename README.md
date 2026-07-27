<div align="center">

# JobCopilot

### Evidence-grounded, human-supervised AI for job applications

JobCopilot turns a raw job description into a structured, reviewable application workflow: offer extraction, profile-memory retrieval, conservative matching, evidence-only email composition, application tracking, Gmail drafts and Calendar follow-ups.

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-Agent%20Orchestration-1C3C3C)
![Streamlit](https://img.shields.io/badge/Streamlit-Private%20Beta-FF4B4B?logo=streamlit&logoColor=white)
![CI](https://github.com/EL-K-Code/Job-Copilot/actions/workflows/ci.yml/badge.svg)
![Status](https://img.shields.io/badge/Status-Private%20Beta-315EFB)

</div>

---

## Product workflow

```text
CV import or manual profile
        ↓
human-verified atomic profile facts
        ↓
job description extraction
        ↓
tenant-scoped FAISS retrieval
        ↓
evidence-aware matching
        ↓
LLM selects memory IDs only
        ↓
deterministic email composition
        ↓
human review
        ↓
tracker / Gmail draft / Calendar follow-up
```

JobCopilot is deliberately not a mass-application bot. It prefers a shorter, honest email over a persuasive claim that cannot be supported by the candidate's verified profile.

---

## Current capabilities

| Capability | Implementation |
| --- | --- |
| Job understanding | Pydantic structured output through OpenAI or Anthropic |
| Profile onboarding | Multiple PDF, DOCX or TXT CVs, or a guided manual form |
| Human verification | Editable keep/remove review before profile activation |
| Candidate memory | Atomic facts with stable IDs, topics, groups and provenance |
| Retrieval | Hugging Face embeddings and tenant-scoped FAISS indexes |
| Matching | Strengths, gaps and evidence-linked candidate claims |
| Email composition | Deterministic prose built from selected verified memory IDs |
| Signature | Authenticated display name, or configured local candidate name |
| Provider resilience | OpenAI primary with optional Anthropic runtime fallback |
| Provider telemetry | Provider, model, operation, status, latency and available usage metadata |
| Application tracking | Tenant-scoped JSON tracker with status, notes and reminders |
| Gmail and Calendar | Per-user OAuth token and explicit human confirmation gates |
| Agent Chat | Per-user graph, tool set, thread namespace and in-memory checkpoint |
| Cost control | Configurable daily AI-operation quota per user |
| Evaluation | Extraction, retrieval and claim-level grounding workflows |
| Delivery | Premium Streamlit UI, Dockerfile and GitHub Actions CI |

---

## Grounding architecture

The language model does not write factual candidate prose freely.

1. Retrieved profile facts are ranked against explicit offer requirements.
2. The LLM may select only one to three existing memory IDs.
3. Deterministic code converts the exact selected memories into first-person claims.
4. Every factual claim is returned in a machine-readable evidence ledger.
5. Unknown IDs, zero-score padding and unsupported strengthening are rejected.

Examples of disallowed amplification include turning:

- `built` into `designed`;
- `works with` into `strong proficiency`;
- one project into `multiple projects`;
- local experimentation into production ownership;
- one technology into adjacent technologies that were never verified.

---

## Private beta isolation

Each authenticated user receives a private workspace:

```text
data/users/<user_id>/
  profile_memories.json
  applications.json
  google_token.json
  usage.json
  faiss_index/
  uploads/
```

The user ID is normalized and validated before any path is resolved. Agent tools receive the authenticated user through Python closures; the model cannot submit or modify a `user_id` tool argument.

The filesystem backend is suitable for a controlled engineering beta. Public production deployment still requires durable database storage, managed authentication, encrypted persistent chat history, rate limiting and managed secrets.

---

## Provider configuration

Copy `.env.example` to `.env` and configure at least one provider:

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=your_local_key
OPENAI_MODEL=gpt-4.1-mini

# Optional runtime fallback
LLM_FALLBACK_PROVIDER=anthropic
ANTHROPIC_API_KEY=
ANTHROPIC_MODEL=claude-sonnet-4-6
```

The primary provider must have a configured key. A fallback without a key is skipped.

Telemetry deliberately excludes:

- prompts;
- CV and job-offer text;
- generated emails;
- API keys;
- raw provider error messages.

---

## Daily beta quotas

A paid AI action consumes one quota unit:

- one CV extraction;
- one application analysis;
- one authenticated Agent Chat turn.

Configure the daily limit:

```env
BETA_DAILY_AI_LIMIT=10
```

Usage is stored separately for each user and resets on the next calendar day. A started provider action counts even when the downstream call fails, which prevents repeated failing retries from creating unbounded cost.

---

## Local setup

```bash
git clone https://github.com/EL-K-Code/Job-Copilot.git
cd Job-Copilot
python -m venv .venv
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Linux or macOS:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create local configuration:

```bash
cp .env.example .env
```

For a personalized signature while authentication is disabled:

```env
LOCAL_CANDIDATE_NAME=Komla Alex LABOU
```

Run the premium private-beta interface:

```bash
python -m streamlit run app/ui/private_beta_app.py
```

Open:

```text
http://localhost:8501
```

---

## Private beta accounts

Enable authentication in `.env`:

```env
BETA_AUTH_ENABLED=true
BETA_USERS_FILE=data/beta_users.json
USER_DATA_ROOT=data/users
```

Create a user:

```bash
python scripts/manage_beta_user.py alex --display-name "Alex"
```

The command stores only a salted PBKDF2 password hash. The account display name is used automatically in generated email signatures.

---

## Profile onboarding

Users can:

- import up to five PDF, DOCX or TXT CV versions;
- combine older role-specific CVs;
- create a profile manually;
- restore an advanced JobCopilot JSON backup.

Raw uploaded CV files are not persisted. Extracted text is sent to the configured model only after explicit consent. No extracted fact becomes active until the user reviews and approves it.

Image-only scanned PDFs are not processed with OCR in the current version.

---

## Google OAuth

To enable Gmail and Calendar locally:

1. create a Google Cloud project;
2. enable Gmail API and Google Calendar API;
3. configure the OAuth consent screen;
4. create a Desktop OAuth client;
5. save the downloaded file as `credentials.json` at the repository root;
6. connect Google from the Settings page.

OAuth credentials and generated tokens are ignored by Git. Each beta user receives a separate token file.

---

## Evaluation

### Extraction

The frozen V1 suite contains 50 synthetic English offers across 10 role families. A separate five-case smoke suite adds French and English preflight coverage.

```bash
python scripts/evaluate_job_extraction.py \
  --dataset evaluation/job_offers.v1.jsonl \
  --benchmark-version 1.0.0
```

### Retrieval

```bash
python scripts/evaluate_retrieval.py
```

Reported metrics include Recall@1/3/5, MRR and NDCG@1/3/5.

### Generated-email grounding

```bash
python scripts/prepare_email_grounding_review.py --limit 10
```

The workflow exports generated emails, selected memories, the claim ledger and privacy-safe provider telemetry for conservative claim-level review.

Current benchmark datasets are synthetic regression suites. They are not evidence of production accuracy or broad job-market generalization.

---

## Validated engineering results

The latest ten-family OpenAI end-to-end run completed:

- 10/10 offers;
- 30/30 successful OpenAI calls;
- no fallback attempt;
- 22/22 supported factual candidate claims;
- zero zero-score claims;
- zero ledger-coverage issues;
- zero technology contamination.

These results validate the frozen test workflow and grounding architecture. They do not measure recruiter response, user acceptance or real-world job-market performance.

---

## Tests and CI

```bash
python -m compileall -q app scripts tests
python scripts/validate_benchmark.py
pytest -q
```

GitHub Actions runs syntax validation, benchmark-integrity checks and the complete unit-test suite on pull requests and pushes to `main`.

---

## Docker

```bash
docker build -t jobcopilot .
```

```bash
docker run --rm -p 8501:8501 \
  --env-file .env \
  -v "$(pwd)/data:/app/data" \
  -v "$(pwd)/credentials.json:/app/credentials.json:ro" \
  jobcopilot
```

The Docker entrypoint launches `app/ui/private_beta_app.py`.

---

## Repository structure

```text
app/
  agent_graph.py
  agent_tools.py
  email_composer.py
  graph.py
  memory.py
  services/
  tools/
  ui/

data/
evaluation/
scripts/
tests/
.github/workflows/
.streamlit/
Dockerfile
PRIVATE_BETA.md
SECURITY.md
```

---

## Current boundaries

- Profile, tracker, usage and OAuth persistence are filesystem-backed.
- Agent Chat history is process-local and disappears after restart.
- Uploaded image-only PDFs are not OCR-processed.
- Token counts depend on provider response metadata and may be unavailable.
- French application quality still needs broader end-to-end testing.
- Public deployment requires managed identity, durable storage, rate limiting and secure secret management.

See [`PRIVATE_BETA.md`](PRIVATE_BETA.md) and [`SECURITY.md`](SECURITY.md) for operational and trust boundaries.
