from __future__ import annotations

from typing import Any
from uuid import uuid4

from langchain_core.tools import BaseTool, tool

from app.auth import load_beta_users
from app.config import settings
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
from app.tools.gmail_tools import create_gmail_draft


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


def build_agent_tools(user_id: str | None = None) -> list[BaseTool]:
    """
    Build one tool set bound to exactly one authenticated workspace.

    The bound user ID and candidate display name are intentionally absent from every
    public tool schema, so the language model cannot select, replace or spoof either value.
    """
    bound_user_id = normalize_user_id(user_id) if user_id is not None else None

    @tool
    def run_jobcopilot_pipeline_tool(job_text: str) -> dict[str, Any]:
        """
        Run the full JobCopilot pipeline on a job offer using the current user's
        private profile memory, then return the structured analysis, match and email.
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
            "email_draft": result["email_draft"],
        }

    @tool
    def create_gmail_draft_tool(
        to: str,
        subject: str,
        body: str,
        confirmed: bool = False,
    ) -> dict[str, Any]:
        """
        Create a Gmail draft in the current user's connected Google account only
        after explicit confirmation of the exact recipient, subject and body.
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
                },
            }
        result = create_gmail_draft(
            to=to,
            subject=subject,
            body=body,
            user_id=bound_user_id,
        )
        return {
            "status": "created",
            "draft": result,
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
        only after explicit confirmation. followup_date must be YYYY-MM-DD.
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

        if has_existing_reminder(
            company=company,
            role=role,
            reminder_date=followup_date,
            user_id=bound_user_id,
        ):
            return {
                "status": "duplicate",
                "message": "A saved application already has this same reminder date.",
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

        return {
            "status": "created",
            "company": company,
            "role": role,
            "followup_date": followup_date,
            "calendar_event": event_result,
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
        """Save an application in the current user's private workspace."""
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
        }

    @tool
    def list_saved_applications_tool() -> list[dict[str, Any]]:
        """List applications from the current user's private workspace only."""
        return [
            record.model_dump()
            for record in load_application_records(user_id=bound_user_id)
        ]

    return [
        run_jobcopilot_pipeline_tool,
        create_gmail_draft_tool,
        create_followup_reminder_tool,
        save_application_record_tool,
        list_saved_applications_tool,
    ]


# Backward-compatible unbound tools used by command-line and test callers.
AGENT_TOOLS = build_agent_tools()
(
    run_jobcopilot_pipeline_tool,
    create_gmail_draft_tool,
    create_followup_reminder_tool,
    save_application_record_tool,
    list_saved_applications_tool,
) = AGENT_TOOLS
