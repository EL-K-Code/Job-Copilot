# JobCopilot Private Beta

The private beta entrypoint adds a user-scoped filesystem workspace and password-gated Streamlit UI without changing the legacy local MVP.

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

The user uploads a verified atomic profile-memory JSON during onboarding. Job analysis, FAISS retrieval, application persistence, Gmail drafts and Calendar events then use that authenticated user's workspace only.

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

## Current boundary

The private beta entrypoint intentionally excludes Agent Chat for now. The current global conversational agent binds static tools and has not yet completed user-context injection through every tool call. The deterministic application workflow is tenant-scoped and covered by cross-user isolation tests.

This is a private engineering beta, not a production identity platform. Deployment behind the public internet still requires HTTPS, secure secret management, rate limiting, persistent database-backed sessions and a production authentication provider.
