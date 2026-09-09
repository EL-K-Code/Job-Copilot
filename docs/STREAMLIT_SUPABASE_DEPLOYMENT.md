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

The tables have Row Level Security enabled and no browser-facing `anon` / `authenticated` table grants. JobCopilot accesses them only from the Streamlit server using the service-role secret.

## 2. Configure local deployment secrets

Never commit these values. Put them in `.env` locally or the Streamlit secret manager in the hosted app.

```env
PERSISTENCE_BACKEND=supabase
SUPABASE_URL=https://YOUR_PROJECT.supabase.co
SUPABASE_SERVICE_ROLE_KEY=YOUR_SERVER_ONLY_SERVICE_ROLE_KEY

OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4.1-mini
OPENAI_PROFILE_MODEL=gpt-4.1-nano

BETA_AUTH_ENABLED=true
BETA_DAILY_AI_LIMIT=10
DEFAULT_TIMEZONE=Europe/Paris
```

`SUPABASE_SERVICE_ROLE_KEY` is a server secret. Never expose it in frontend code, screenshots, GitHub files or browser JavaScript.

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

In **Advanced settings / Secrets**, add the same server-side values shown above. Do not add `.env`, `credentials.json`, OAuth tokens or `secrets.toml` to Git.

Recommended public demo configuration:

```env
PERSISTENCE_BACKEND=supabase
BETA_AUTH_ENABLED=true
BETA_DAILY_AI_LIMIT=5
```

A low recruiter/demo quota protects the OpenAI account from accidental or abusive usage.

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

Google OAuth tokens are intentionally **not** migrated to Supabase by this deployment change. Gmail and Calendar remain optional and should only be enabled after a secure hosted token-storage design is configured. The core recruiter demo does not require them.

## 6. Recruiter sharing checklist

Before sharing a live URL:

1. Run `supabase/schema.sql` successfully.
2. Set `PERSISTENCE_BACKEND=supabase` and the two Supabase secrets.
3. Keep `BETA_AUTH_ENABLED=true`.
4. Create a dedicated recruiter/tester account.
5. Keep `BETA_DAILY_AI_LIMIT` low (for example 5).
6. Test one CV import, one application analysis, logout/login and an app reboot to confirm persistence.
7. Share the Streamlit URL plus the dedicated credentials through a private channel.

After this passes, the live URL can be added to the JobCopilot README and GitHub profile as a recruiter-facing demo.
