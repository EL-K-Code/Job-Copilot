from __future__ import annotations

from typing import Any
from uuid import uuid4

from langchain_core.tools import BaseTool, tool

from app.auth import load_beta_users
from app.config import settings
from app.services.application_workflow import (
    external_action_already_recorded,
    external_action_key,
    get_workflow_snapshot,
    list_workflow_snapshots,
    mark_application_applied,
    record_external_action,
    request_application_approval,
    set_application_outcome,
    workflow_snapshot,
)
from app.services.applications_store import (
    add_application_record,
    create_application_record,
    find_existing_application,
    has_existing_reminder,
    load_application_records,
)
from app.tenancy import DEFAULT_LOCAL_USER_ID, normalize_user_id
from app.tools.calendar_tools import (
    build_followup_event_payload,
    create_followup_event,
)
from app.tools.gmail_tools import create_gmail_draft, google_token_exists


def _candidate_name_for_user(user_id: str | None) -> str:
    """Resolve a trusted server-side display name without exposing it to tool inputs."""
    if user_id is None:
        return settings.local_candidate_name
    if user_id == DEFAULT_LOCAL_USER_ID:
        return settings.local_candidate_name
    if not settings.beta_auth_enabled:
        return ""
    user = load_beta_users().get(user_id, {})
    return str(user.get("display_name", "")).strip()


def _hosted_google_connection_required() -> bool:
    return bool(
        settings.hosted_recruiter_demo
        and getattr(settings, "hosted_google_oauth_enabled", False)
    )


def build_agent_tools(
    user_id: str | None = None,
    *,
    include_google: bool | None = None,
) -> list[BaseTool]:
    """
    Build one tool set bound to exactly one authenticated workspace.

    The bound user ID and candidate display name are intentionally absent from every
    public tool schema, so the language model cannot select, replace or spoof either value.
    Hosted recruiter demos expose Google tools only when hosted OAuth is explicitly enabled.
    """
    bound_user_id = normalize_user_id(user_id) if user_id is not None else None
    if include_google is None:
        include_google = (
            not settings.hosted_recruiter_demo
            or bool(getattr(settings, "hosted_google_oauth_enabled", False))
        )

    @tool
    def run_jobcopilot_pipeline_tool(job_text: str) -> dict[str, Any]:
        """
        Run the full JobCopilot pipeline on a job offer using the current user's
        private profile memory. Return the structured role analysis, evidence match,
        recommended application route and grounded application pack. This analysis is
        read-only with respect to the application tracker.
        """
        from app.graph import jobcopilot_graph

        state: dict[str, Any] = {
            "job_text": job_text,
            "candidate_name": _candidate_name_for_user(bound_user_id),
        }
        if bound_user_id is not None:
            state["user_id"] = bound_user_id

        result = jobcopilot_graph.invoke(
            state,
            config={
                "configurable": {
                    "thread_id": (
                        f"agent-jobcopilot-pipeline-{bound_user_id or 'local'}-{uuid4()}"
                    )
                }
            },
        )

        return {
            "job_analysis": result["job_analysis"],
            "retrieved_memories": result["retrieved_memories"],
            "match_insight": result["match_insight"],
            "application_pack": result["application_pack"],
            "email_draft": result["email_draft"],
        }

    @tool
    def create_gmail_draft_tool(
        to: str,
        subject: str,
        body: str,
        confirmed: bool = False,
        company: str = "",
        role: str = "",
    ) -> dict[str, Any]:
        """
        Create a Gmail draft in the current user's connected Google account only
        after explicit confirmation of the exact recipient, subject and body.
        When company and role identify a saved workflow, successful retries are
        idempotent and an audit event is appended without storing OAuth credentials.
        """
        if not confirmed:
            return {
                "status": "confirmation_required",
                "message": (
                    "Explicit user confirmation is required before creating the Gmail draft."
                ),
                "preview": {
                    "to": to,
                    "subject": subject,
                    "body": body,
                    "company": company,
                    "role": role,
                },
            }
        if (
            bound_user_id is not None
            and _hosted_google_connection_required()
            and not google_token_exists(bound_user_id)
        ):
            return {
                "status": "google_not_connected",
                "message": "Connect Google in Settings before creating a Gmail draft.",
            }

        workflow = (
            get_workflow_snapshot(company, role, user_id=bound_user_id)
            if company.strip() and role.strip()
            else None
        )
        action_key = external_action_key(
            "gmail_draft_created",
            company,
            role,
            to,
            subject,
            body,
        )
        if workflow and external_action_already_recorded(
            company,
            role,
            action_key,
            user_id=bound_user_id,
        ):
            return {
                "status": "duplicate",
                "message": "This exact Gmail draft action was already completed for the application.",
                "action_key": action_key,
            }

        result = create_gmail_draft(
            to=to,
            subject=subject,
            body=body,
            user_id=bound_user_id,
        )
        if workflow:
            record_external_action(
                company,
                role,
                action_type="gmail_draft_created",
                action_key=action_key,
                user_id=bound_user_id,
                actor="agent",
                detail=f"Gmail draft created for recipient {to.strip()}.",
            )
        return {
            "status": "created",
            "draft": result,
            "action_key": action_key if workflow else "",
        }

    @tool
    def create_followup_reminder_tool(
        company: str,
        role: str,
        followup_date: str,
        confirmed: bool = False,
    ) -> dict[str, Any]:
        """
        Create a Calendar follow-up in the current user's connected Google account
        only after explicit confirmation. followup_date must be YYYY-MM-DD. Saved
        workflows use an idempotency key so a retry cannot create a second event.
        """
        if not confirmed:
            return {
                "status": "confirmation_required",
                "message": (
                    "Explicit user confirmation is required before creating the Calendar event."
                ),
                "preview": {
                    "company": company,
                    "role": role,
                    "followup_date": followup_date,
                },
            }
        if (
            bound_user_id is not None
            and _hosted_google_connection_required()
            and not google_token_exists(bound_user_id)
        ):
            return {
                "status": "google_not_connected",
                "message": "Connect Google in Settings before creating a Calendar reminder.",
            }

        workflow = get_workflow_snapshot(
            company,
            role,
            user_id=bound_user_id,
        )
        action_key = external_action_key(
            "calendar_followup_created",
            company,
            role,
            followup_date,
        )
        if workflow:
            if external_action_already_recorded(
                company,
                role,
                action_key,
                user_id=bound_user_id,
            ):
                return {
                    "status": "duplicate",
                    "message": "This exact Calendar follow-up action was already completed.",
                    "action_key": action_key,
                }
        elif has_existing_reminder(
            company=company,
            role=role,
            reminder_date=followup_date,
            user_id=bound_user_id,
        ):
            # Backward-compatible protection for records created before workflow action keys.
            return {
                "status": "duplicate",
                "message": "A legacy saved application already has this same reminder date.",
            }

        payload = build_followup_event_payload(
            company=company,
            role=role,
            followup_date=followup_date,
        )
        event_result = create_followup_event(
            **payload,
            user_id=bound_user_id,
        )

        if workflow:
            record_external_action(
                company,
                role,
                action_type="calendar_followup_created",
                action_key=action_key,
                user_id=bound_user_id,
                actor="agent",
                detail=f"Google Calendar follow-up created for {followup_date}.",
                reminder_date=followup_date,
            )

        return {
            "status": "created",
            "company": company,
            "role": role,
            "followup_date": followup_date,
            "calendar_event": event_result,
            "action_key": action_key if workflow else "",
        }

    @tool
    def save_application_record_tool(
        company: str,
        role: str,
        email_subject: str = "",
        email_body: str = "",
        reminder_date: str = "",
        notes: str = "",
    ) -> dict[str, Any]:
        """
        Save a grounded application in the current user's private workspace.
        A newly saved legacy-compatible draft maps to the Ready to apply workflow stage.
        """
        existing = find_existing_application(
            company=company,
            role=role,
            user_id=bound_user_id,
        )

        if existing:
            return {
                "status": "duplicate",
                "message": "Application already exists.",
                "existing_record": existing.model_dump(),
                "workflow": workflow_snapshot(existing),
            }

        record = create_application_record(
            company=company,
            role=role,
            email_subject=email_subject,
            email_body=email_body,
            reminder_date=reminder_date,
            notes=notes,
            source="agent",
            status="drafted",
        )

        saved = add_application_record(record, user_id=bound_user_id)

        if not saved:
            return {
                "status": "duplicate",
                "message": "Application already exists.",
            }

        return {
            "status": "saved",
            "record": record.model_dump(),
            "workflow": workflow_snapshot(record),
        }

    @tool
    def get_application_workflow_tool(company: str, role: str) -> dict[str, Any]:
        """Inspect the deterministic lifecycle stage and next safe actions for one saved application."""
        snapshot = get_workflow_snapshot(
            company,
            role,
            user_id=bound_user_id,
        )
        if snapshot is None:
            return {
                "status": "not_found",
                "message": "Save the application to the tracker before advancing its workflow.",
            }
        return {"status": "ok", "workflow": snapshot}

    @tool
    def prepare_application_for_approval_tool(company: str, role: str) -> dict[str, Any]:
        """
        Move a saved Ready to apply application to Awaiting approval. This is an
        internal state change only: it does not send email, submit a portal form or
        create a Calendar event.
        """
        try:
            updated = request_application_approval(
                company,
                role,
                user_id=bound_user_id,
                actor="agent",
            )
        except ValueError as exc:
            return {"status": "invalid_transition", "message": str(exc)}
        return {
            "status": "awaiting_approval",
            "workflow": workflow_snapshot(updated),
            "message": "Application is awaiting explicit human approval before submission actions.",
        }

    @tool
    def mark_application_applied_tool(
        company: str,
        role: str,
        confirmed: bool = False,
    ) -> dict[str, Any]:
        """
        Mark an application as actually submitted/sent only after the user explicitly
        confirms that fact. This tool never submits an ATS form or sends Gmail itself.
        """
        snapshot = get_workflow_snapshot(company, role, user_id=bound_user_id)
        if snapshot is None:
            return {"status": "not_found", "message": "Application workflow not found."}
        if not confirmed:
            return {
                "status": "confirmation_required",
                "message": "Confirm only after the application was actually submitted or sent.",
                "preview": {
                    "company": company,
                    "role": role,
                    "current_stage": snapshot["stage"],
                    "target_stage": "applied",
                },
            }
        try:
            updated = mark_application_applied(
                company,
                role,
                user_id=bound_user_id,
                actor="agent",
            )
        except ValueError as exc:
            return {"status": "invalid_transition", "message": str(exc)}
        return {"status": "applied", "workflow": workflow_snapshot(updated)}

    @tool
    def update_application_outcome_tool(
        company: str,
        role: str,
        outcome: str,
        confirmed: bool = False,
    ) -> dict[str, Any]:
        """
        Record a user-reported outcome: interview, rejected, offer or closed.
        Explicit confirmation is required so the model cannot infer an outcome.
        """
        if outcome not in {"interview", "rejected", "offer", "closed"}:
            return {
                "status": "invalid_outcome",
                "message": "Outcome must be interview, rejected, offer or closed.",
            }
        if not confirmed:
            return {
                "status": "confirmation_required",
                "message": "Confirm the reported application outcome before updating the tracker.",
                "preview": {
                    "company": company,
                    "role": role,
                    "outcome": outcome,
                },
            }
        try:
            updated = set_application_outcome(
                company,
                role,
                outcome,
                user_id=bound_user_id,
                actor="agent",
            )
        except ValueError as exc:
            return {"status": "invalid_transition", "message": str(exc)}
        return {"status": "updated", "workflow": workflow_snapshot(updated)}

    @tool
    def list_saved_applications_tool() -> list[dict[str, Any]]:
        """List applications and effective workflow stages from the current user's private workspace only."""
        records = load_application_records(user_id=bound_user_id)
        snapshots = {
            (item["company"].casefold(), item["role"].casefold()): item
            for item in list_workflow_snapshots(bound_user_id)
        }
        output = []
        for record in records:
            payload = record.model_dump()
            payload["workflow"] = snapshots.get(
                (record.company.casefold(), record.role.casefold()),
                workflow_snapshot(record),
            )
            output.append(payload)
        return output

    core_tools = [
        run_jobcopilot_pipeline_tool,
        save_application_record_tool,
        get_application_workflow_tool,
        prepare_application_for_approval_tool,
        mark_application_applied_tool,
        update_application_outcome_tool,
        list_saved_applications_tool,
    ]
    if not include_google:
        return core_tools

    return [
        run_jobcopilot_pipeline_tool,
        create_gmail_draft_tool,
        create_followup_reminder_tool,
        save_application_record_tool,
        get_application_workflow_tool,
        prepare_application_for_approval_tool,
        mark_application_applied_tool,
        update_application_outcome_tool,
        list_saved_applications_tool,
    ]


# Backward-compatible named tools for command-line and direct test callers.
_LEGACY_AGENT_TOOLS = build_agent_tools(include_google=True)
_LEGACY_AGENT_TOOL_MAP = {current.name: current for current in _LEGACY_AGENT_TOOLS}
run_jobcopilot_pipeline_tool = _LEGACY_AGENT_TOOL_MAP["run_jobcopilot_pipeline_tool"]
create_gmail_draft_tool = _LEGACY_AGENT_TOOL_MAP["create_gmail_draft_tool"]
create_followup_reminder_tool = _LEGACY_AGENT_TOOL_MAP["create_followup_reminder_tool"]
save_application_record_tool = _LEGACY_AGENT_TOOL_MAP["save_application_record_tool"]
get_application_workflow_tool = _LEGACY_AGENT_TOOL_MAP["get_application_workflow_tool"]
prepare_application_for_approval_tool = _LEGACY_AGENT_TOOL_MAP[
    "prepare_application_for_approval_tool"
]
mark_application_applied_tool = _LEGACY_AGENT_TOOL_MAP["mark_application_applied_tool"]
update_application_outcome_tool = _LEGACY_AGENT_TOOL_MAP["update_application_outcome_tool"]
list_saved_applications_tool = _LEGACY_AGENT_TOOL_MAP["list_saved_applications_tool"]

# The default graph-facing tool list respects the active deployment boundary.
AGENT_TOOLS = build_agent_tools()
