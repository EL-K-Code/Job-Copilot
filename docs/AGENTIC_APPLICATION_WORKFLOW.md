# Supervised agentic application workflow

JobCopilot Phase 3 separates **LLM reasoning** from **workflow authority**.

The model may analyze an offer, retrieve verified profile evidence and recommend application material. It does not have authority to silently decide that an application was submitted, that a recruiter replied, or that an outcome occurred.

## Lifecycle

```text
DISCOVERED
   ↓
ANALYZED
   ↓
READY_TO_APPLY
   ↓
AWAITING_APPROVAL
   ↓
APPLIED
   ↓
FOLLOW_UP_DUE
   ↓
INTERVIEW ─────→ OFFER ─────→ CLOSED
   │
   └────────────→ REJECTED ─→ CLOSED
```

`APPLIED` may also move directly to `INTERVIEW`, `REJECTED`, `OFFER` or `CLOSED`. `FOLLOW_UP_DUE` is derived when an applied record reaches its persisted reminder date, so JobCopilot does not need a background mutation at midnight merely to display that a follow-up is due.

## Authority boundaries

### LLM / LangGraph may

- analyze the supplied job description;
- extract the explicit application route;
- retrieve verified candidate evidence;
- build grounded application content;
- inspect the current workflow stage;
- propose the next lifecycle action;
- prepare a confirmed Gmail draft or Calendar reminder through the existing tools.

### Deterministic application code owns

- valid lifecycle transitions;
- legacy-status compatibility;
- the follow-up due rule;
- external-action idempotency keys;
- the workflow audit trail;
- persistence of the current stage.

### Human confirmation remains required

- before Gmail or Calendar side effects;
- before recording an application as actually submitted or sent;
- before recording interview, rejection or offer outcomes.

A Gmail **draft** is never interpreted as an application being sent. A Calendar **reminder** is never interpreted as a follow-up having happened.

## State persistence

Phase 3 adds lifecycle fields to the existing `ApplicationRecord` JSON payload:

- `application_id`;
- `workflow_stage`;
- `application_channel`;
- `workflow_history`;
- `external_action_keys`;
- `updated_at`.

No new Supabase table or migration is required. Hosted deployments continue to persist the `applications` namespace in the existing `jobcopilot_state` store.

Older records remain readable. Their legacy tracker status is mapped conservatively:

| Legacy status | Effective workflow stage |
| --- | --- |
| `drafted` | `ready_to_apply` |
| `applied` | `applied` |
| `follow_up` | `follow_up_due` |
| `interview` | `interview` |
| `closed` | `closed` |

## Idempotent side effects

When a Gmail or Calendar action is tied to a saved workflow, JobCopilot derives a deterministic SHA-256-based action key from the material action inputs.

A successful action records that key in the application record. Repeating the exact same tool call then returns a duplicate result instead of creating a second side effect.

The audit trail records action type, actor, timestamp, stage and the action key. OAuth credentials, provider secrets, prompts and CV text are not written to the workflow audit trail.

## User surfaces

### New application

After analysis, the user can explicitly choose **Track as ready to apply**. Analysis itself stays read-only until that choice is made.

The application workspace then exposes the approval gate and lifecycle progression without pretending that an internal state transition is a real-world submission.

### Applications

The workflow-aware tracker shows:

- current effective stage;
- application route;
- follow-up date;
- external-action count;
- recommended next action;
- lifecycle controls;
- append-only audit events.

### Agent Chat

Tenant-bound tools expose lifecycle inspection and controlled transitions. `user_id` remains server-bound and is absent from model-facing tool schemas.

## Engineering intent

Phase 3 is not designed as a mass-application bot. Its purpose is to demonstrate a production-oriented agent architecture in which:

1. LLM reasoning handles ambiguous language tasks;
2. retrieval and grounding constrain candidate claims;
3. deterministic code owns business state and transition validity;
4. external side effects are confirmed and idempotent;
5. humans retain authority over consequential real-world facts.
