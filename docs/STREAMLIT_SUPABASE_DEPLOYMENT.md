# Streamlit Community Cloud + Supabase deployment

This is the supported private-beta deployment path for JobCopilot.

## 1. Create the Supabase project

Create a free Supabase project, then open **SQL Editor** and run:

```sql
-- copy/paste the repository file: supabase/schema.sql
```

The schema creates:

- `jobcopilot_state` for tenant-scoped profile, application and beta-user JSON state;
- `jobcopilot_usage` for durable daily AI quotas;
- `jobcopilot_consume_quota(...)`, an atomic Postgres function that prevents concurrent sessions from racing past a user's daily limit.

The tables have Row Level Security enabled and no browser-facing `anon` / `authenticated` table grants. JobCopilot accesses them only from the trusted Streamlit server using an elevated Supabase server secret.

## 2. Configure local deployment secrets

Never commit these values. For local development, put them in `.env`:

```env
PERSISTENCE_BACKEND=supabase
SUPABASE_URL=https://YOUR_PROJECT.supabase.co
SUPABASE_SECRET_KEY=sb_secret_...

OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4.1-mini
OPENAI_PROFILE_MODEL=gpt-4.1-nano

BETA_AUTH_ENABLED=true
BETA_DAILY_AI_LIMIT=10
DEFAULT_TIMEZONE=Europe/Paris
```

Use the current Supabase **Secret key** (`sb_secret_...`) from the project's Connect / API Keys view. It is server-only and bypasses RLS, so never expose it in frontend code, screenshots, GitHub files or browser JavaScript. JobCopilot sends current secret keys only through the `apikey` header. Legacy JWT `SUPABASE_SERVICE_ROLE_KEY` remains supported as a migration fallback, but new deployments should use `SUPABASE_SECRET_KEY`.

`HOSTED_RECRUITER_DEMO` should normally remain `false` for local development so Gmail and Calendar can still be tested locally with a configured Google OAuth client.

## 3. Create a private beta account

With the Supabase variables configured in your local shell or `.env`:

```bash
python scripts/create_beta_user.py recruiter-demo --display-name "Recruiter Demo"
```

The script prompts for the password without putting it in shell history. Only a salted PBKDF2 hash is persisted.

Create a separate account for each tester instead of sharing one password. This keeps profile data, tracker state and quota usage isolated.

## 4. Deploy on Streamlit Community Cloud

Create a new app from:

- repository: `EL-K-Code/Job-Copilot`
- branch: `main`
- entrypoint: `app/ui/private_beta_app.py`

In **Advanced settings / Secrets**, Streamlit expects TOML. Paste root-level secrets like this:

```toml
PERSISTENCE_BACKEND = "supabase"
SUPABASE_URL = "https://YOUR_PROJECT.supabase.co"
SUPABASE_SECRET_KEY = "sb_secret_..."
OPENAI_API_KEY = "..."
OPENAI_MODEL = "gpt-4.1-mini"
OPENAI_PROFILE_MODEL = "gpt-4.1-nano"
BETA_AUTH_ENABLED = "true"
BETA_DAILY_AI_LIMIT = "5"
DEFAULT_TIMEZONE = "Europe/Paris"
HOSTED_RECRUITER_DEMO = "true"
```

Root-level Streamlit secrets are exposed to the app as environment variables, so JobCopilot's existing configuration loader can consume them. Do not add `.env`, `credentials.json`, OAuth tokens or `.streamlit/secrets.toml` to Git.

A low recruiter/demo quota protects the OpenAI account from accidental or abusive usage.

`HOSTED_RECRUITER_DEMO=true` is an explicit product boundary for the hosted demo. It:

- keeps offer extraction, profile retrieval, evidence-aware matching and the application pack;
- keeps the persistent application tracker and data export/deletion controls;
- removes Google connection status and OAuth controls from the hosted UI;
- removes Gmail and Calendar actions from the hosted application workflow;
- removes Gmail and Calendar tools from the authenticated Agent Chat toolset;
- tells the agent that external Google actions are unavailable in this deployment.

This is stronger than merely disabling buttons: the hosted authenticated agent does not receive those tools.

## 5. What is durable and what is disposable

Durable in Supabase:

- verified profile memories;
- application tracker records;
- private-beta account hashes and display names;
- per-user daily AI usage.

Disposable / rebuilt on the Streamlit instance:

- FAISS indexes (rebuilt from verified profile memories);
- Hugging Face public embedding-model cache;
- temporary CV upload bytes (source CV files are not persisted by JobCopilot).

Google OAuth tokens are intentionally **not** migrated to Supabase by this deployment change. Gmail and Calendar remain optional for local development and are intentionally unavailable in the hosted recruiter demo.

Deleting a user's application/profile data removes their verified profile, tracker and quota ledger but deliberately preserves the private-beta login record so the same account can start over safely.

## 6. Recruiter sharing checklist

Before sharing a live URL:

1. Run `supabase/schema.sql` successfully.
2. Set `PERSISTENCE_BACKEND=supabase`, `SUPABASE_URL` and `SUPABASE_SECRET_KEY`.
3. Set `HOSTED_RECRUITER_DEMO=true`.
4. Keep `BETA_AUTH_ENABLED=true`.
5. Create a dedicated recruiter/tester account.
6. Keep `BETA_DAILY_AI_LIMIT` low (for example 5).
7. Confirm the hosted UI contains no Google connection, Gmail-draft or Calendar-action controls.
8. Confirm Agent Chat cannot see Gmail or Calendar tools.
9. Test one CV import, one application analysis, one tracker save, logout/login and an app reboot to confirm persistence.
10. Test data export and application-data deletion once with a disposable tester account.
11. Share the Streamlit URL plus the dedicated credentials through a private channel.

After this passes, the live URL can be added to the JobCopilot README and GitHub profile as a recruiter-facing demo.
