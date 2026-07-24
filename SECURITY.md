# Security and Responsible Use

JobCopilot is a local engineering MVP that processes job descriptions, candidate profile memories and application records. It can also create Gmail drafts and Google Calendar events when local OAuth access is configured.

## Trust boundaries

- Job descriptions are untrusted text input.
- Candidate memories and application records may contain personal data.
- OAuth credentials and tokens grant access to external Google services.
- Persisted FAISS indexes contain pickle-backed metadata and must be treated as trusted local artifacts only.

## External-action policy

The tool-calling agent must never create a Gmail draft or Calendar event without explicit confirmation of the exact proposed action in the current conversation turn.

- Gmail confirmation must cover recipient, subject and body.
- Calendar confirmation must cover company, role and date.
- A missing or ambiguous confirmation must not trigger the action.
- The Streamlit action buttons count as direct user approval because the user reviews the editable values before clicking them.

## Secret handling

Never commit:

- `.env` files containing secrets;
- `credentials.json`;
- OAuth tokens;
- private candidate memories;
- real application records;
- production logs containing personal information.

Use `.env.example` only as a variable-name template.

## FAISS index handling

Loading a persisted LangChain FAISS store requires pickle deserialization. JobCopilot therefore rebuilds its in-memory index from `profile_memories.json` by default.

Set `ALLOW_TRUSTED_FAISS_DESERIALIZATION=true` only when the index was generated locally by you, has not been modified by another party and remains on a trusted machine. Never enable this for an uploaded or downloaded index.

## Deployment warning

The current repository is not designed for an unauthenticated multi-user deployment. Before deploying it beyond a trusted local environment, add:

- authentication and authorization;
- per-user data and session isolation;
- encrypted secret storage;
- durable transactional persistence;
- audit logging with personal-data redaction;
- rate limits and abuse controls;
- explicit approval records for external actions;
- retention and deletion policies.

## Reporting a vulnerability

Do not disclose credentials, personal profile data or OAuth tokens in a public issue. Contact the repository owner privately with a minimal reproduction that uses synthetic data.
