# Streamlit Community Cloud + Supabase deployment

This is the supported private-beta deployment path for JobCopilot.

## 1. Create the Supabase project

Create a Supabase project, then open **SQL Editor** and run:

```sql
-- copy/paste the repository file: supabase/schema.sql
```

The schema creates:

- `jobcopilot_state` for tenant-scoped profile, application, beta-user and encrypted OAuth state;
- `jobcopilot_usage` for durable daily AI quotas;
- `jobcopilot_consume_quota(...)`, an atomic Postgres function that prevents concurrent sessions from racing past a user's daily limit.

The tables have Row Level Security enabled and no browser-facing `anon` / `authenticated` table grants. JobCopilot accesses them only from trusted Streamlit server code using an elevated Supabase server secret.

## 2. Configure core deployment secrets

Never commit these values. For local development, put them in `.env`; for Streamlit Community Cloud, use **App settings → Secrets**.

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

Use the current Supabase **Secret key** (`sb_secret_...`) from the project's Connect / API Keys view. It is server-only and bypasses RLS, so never expose it in frontend code, screenshots, GitHub files or browser JavaScript. JobCopilot sends current secret keys only through the `apikey` header. Legacy JWT `SUPABASE_SERVICE_ROLE_KEY` remains supported as a migration fallback.

## 3. Create a private beta account

With the Supabase variables configured locally:

```bash
python scripts/create_beta_user.py recruiter-demo --display-name "Recruiter Demo"
```

The script prompts for the password without putting it in shell history. Only a salted PBKDF2 hash is persisted.

## 4. Deploy on Streamlit Community Cloud

Create the app from:

- repository: `EL-K-Code/Job-Copilot`
- branch: `main`
- entrypoint: `app/ui/private_beta_app.py`

Root-level Streamlit TOML secrets are exposed to the app as environment variables. Do not add `.env`, `credentials.json`, OAuth tokens or `.streamlit/secrets.toml` to Git.

## 5. Optional hosted Google OAuth

Hosted Gmail/Calendar actions are opt-in. Local development can still use the installed-app flow, while Streamlit uses a separate Google **Web application** OAuth client.

In Google Cloud:

1. Enable **Gmail API** and **Google Calendar API**.
2. Configure the Google Auth consent screen.
3. For an External app still in testing, add every allowed tester under **Audience → Test users**.
4. Add these scopes under **Data Access**:
   - `https://www.googleapis.com/auth/gmail.compose`
   - `https://www.googleapis.com/auth/calendar.events`
5. Create an OAuth client with application type **Web application**.
6. Add the exact Streamlit app URL as an authorized redirect URI. For the current deployment this is:

```text
https://jobcopilot-recruiter-ai.streamlit.app/
```

Then add these Streamlit secrets:

```toml
HOSTED_GOOGLE_OAUTH_ENABLED = "true"
GOOGLE_OAUTH_CLIENT_ID = "...apps.googleusercontent.com"
GOOGLE_OAUTH_CLIENT_SECRET = "..."
GOOGLE_OAUTH_REDIRECT_URI = "https://jobcopilot-recruiter-ai.streamlit.app/"
GOOGLE_TOKEN_ENCRYPTION_KEY = "a-high-entropy-server-secret-of-at-least-32-characters"
```

`GOOGLE_TOKEN_ENCRYPTION_KEY` is server-only. JobCopilot derives an encryption key from it and encrypts Google access/refresh credentials before storing them in the `google_oauth` namespace of `jobcopilot_state`.

The OAuth callback uses a short-lived HMAC-signed state token bound to the authenticated private-beta user. This allows the callback to restore the correct tenant after the browser leaves Streamlit for Google's consent screen.

When hosted OAuth is enabled:

- Settings shows **Connect Google securely** / **Disconnect Google**;
- Gmail draft and Calendar reminder actions become available after connection;
- Agent Chat receives the Google tools again;
- every external action still requires explicit user confirmation;
- disconnecting Google removes the persistent encrypted OAuth credential state;
- deleting the tester's application data also deletes their Google OAuth credentials;
- OAuth tokens are never included in user exports.

If hosted Google OAuth is disabled, the recruiter demo retains the previous fail-closed behavior and exposes no Gmail/Calendar actions.

### Google verification note

`gmail.compose` is a restricted Gmail scope. For a small private beta, keep the Google Auth app in **Testing** and add only approved test users. A broader public release may require Google's OAuth verification process and, depending on how restricted-scope data is handled, additional security review.

## 6. What is durable and what is disposable

Durable in Supabase:

- verified profile memories;
- application tracker records;
- private-beta account hashes and display names;
- per-user daily AI usage;
- encrypted hosted Google OAuth credentials when enabled.

Disposable / rebuilt on the Streamlit instance:

- FAISS indexes (rebuilt from verified profile memories);
- Hugging Face public embedding-model cache;
- temporary CV upload bytes.

Raw uploaded CV files are not persisted by JobCopilot.

## 7. Recruiter sharing checklist

Before sharing a live URL:

1. Confirm `supabase/schema.sql` is applied.
2. Confirm `PERSISTENCE_BACKEND=supabase`, `SUPABASE_URL` and `SUPABASE_SECRET_KEY`.
3. Keep `HOSTED_RECRUITER_DEMO=true` and `BETA_AUTH_ENABLED=true`.
4. Create a dedicated recruiter/tester account and keep `BETA_DAILY_AI_LIMIT` low.
5. Test one CV import, application analysis, tracker save, logout/login and app reboot.
6. If hosted Google OAuth is enabled, connect a Google test account and verify one Gmail draft plus one Calendar reminder.
7. Verify both external actions require explicit confirmation.
8. Disconnect Google and confirm actions stop working until reconnect.
9. Test data export and application-data deletion with a disposable tester account.
10. Share the Streamlit URL plus dedicated credentials through a private channel.
