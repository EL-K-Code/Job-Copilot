# JobCopilot Private Beta

The private beta entrypoint adds a user-scoped filesystem workspace, password-gated Streamlit UI and tenant-safe Agent Chat without changing the legacy local MVP.

## What is isolated

Each authenticated user receives a dedicated directory under `USER_DATA_ROOT`:

```text
data/users/<user_id>/
  profile_memories.json
  applications.json
  google_token.json
  faiss_index/
  uploads/
```

The application resolves these paths from a validated `user_id`. Path separators, traversal sequences and unsafe identifiers are rejected.

Agent Chat uses a separate tool set, LangGraph instance, in-memory checkpointer and namespaced conversation thread for each authenticated user. The user ID is bound in Python and is not exposed in the model's tool schemas.

## Configure the LLM provider

JobCopilot supports OpenAI and Anthropic for structured extraction, matching, evidence selection, CV profile extraction and Agent Chat.

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=your_local_openai_key
OPENAI_MODEL=gpt-4.1-mini

# Optional automatic fallback when the primary provider fails
LLM_FALLBACK_PROVIDER=anthropic
ANTHROPIC_API_KEY=your_local_anthropic_key
ANTHROPIC_MODEL=claude-sonnet-4-6
```

The primary provider must have a configured key. A fallback provider without a key is skipped rather than blocking startup. Never commit real API keys; use local environment files or the deployment secret store.

GitHub Actions uses the repository secret `OPENAI_API_KEY` when OpenAI is selected. If both provider secrets exist, the workflows automatically configure the other provider as a fallback.

## Enable private beta authentication

In `.env`:

```env
BETA_AUTH_ENABLED=true
BETA_USERS_FILE=data/beta_users.json
USER_DATA_ROOT=data/users
```

Create the first account locally:

```bash
python scripts/manage_beta_user.py alice --display-name "Alice"
```

The command prompts for the password without echoing it and stores only a salted PBKDF2 hash.

## Run the private beta frontend

```bash
streamlit run app/ui/private_beta_app.py \
  --server.address 127.0.0.1 \
  --server.port 8501
```

## Profile onboarding

A normal tester never needs to create or edit the internal atomic-memory JSON directly.

The first-use screen offers three routes:

1. **Import CVs** — up to five PDF, DOCX or TXT files can be combined. Text is extracted locally; the original files are not persisted. After explicit consent, extracted text is sent to the configured LLM to propose conservative atomic facts.
2. **Fill manually** — guided fields cover professional summary, experience, projects, education, technical skills, languages, certifications, achievements and career preferences.
3. **Advanced restore** — a previously exported `profile_memories.json` file can be restored after review.

Every route ends in the same editable review table. The user can keep, edit, delete or add facts. Nothing becomes application evidence until the user activates the reviewed profile.

The dedicated **Profile** page then supports:

- reviewing all current verified facts and their sources;
- importing another CV version;
- adding facts manually;
- merging verified facts with the active profile;
- replacing the profile after explicit review;
- rebuilding the tenant-scoped FAISS index through the existing profile store.

Image-only scanned PDFs do not use OCR in the private beta. Users should provide a text PDF, DOCX or TXT file instead.

## Tenant-safe Agent Chat

The Agent Chat tab can:

- analyze a job against the authenticated user's profile;
- list and save applications in that user's workspace;
- prepare Gmail drafts and Calendar reminders using that user's Google token;
- perform external actions only after explicit confirmation.

The language model cannot supply or change a `user_id`. Every tool is constructed as a closure already bound to the authenticated account. Alice and Bob also receive different agent graphs and different in-memory checkpoints, so a thread-ID collision cannot cross tenant boundaries.

Chat history is currently process-local. Restarting the server clears conversations, and the beta does not yet provide durable encrypted chat-history storage.

## Google connection

A Google OAuth client file remains shared server configuration. Each user's refresh/access token is stored separately:

```bash
python -m app.bootstrap_gmail_auth --user-id alice
```

The private beta UI also exposes a local interactive connection button.

## Privacy controls

The Settings page supports:

- export of profile memories and application records;
- deletion of the complete private workspace, including Google tokens and FAISS indexes;
- explicit display of whether Google is connected for the current user.

Provider telemetry stores provider, model, operation, status, latency and available token counts. It deliberately excludes prompts, CV text, generated content, API keys and raw provider errors.

## Current boundary

This is a private engineering beta, not a production identity platform. Deployment behind the public internet still requires HTTPS, secure secret management, rate limiting, persistent database-backed sessions, encrypted durable chat storage and a production authentication provider.
