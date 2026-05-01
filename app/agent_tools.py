from __future__ import annotations

from typing import Any

from langchain_core.tools import tool

from app.services.applications_store import (
    add_application_record,
    create_application_record,
    find_existing_application,
    has_existing_reminder,
    load_application_records,
)
from app.tools.calendar_tools import (
    build_followup_event_payload,
    create_followup_event,
)
from app.tools.gmail_tools import create_gmail_draft


@tool
def run_jobcopilot_pipeline_tool(job_text: str) -> dict[str, Any]:
    """
    Run the full JobCopilot pipeline on a job offer:
    analyze the job, retrieve profile memory, generate match insight,
    and draft a tailored application email.
    """
    from app.graph import jobcopilot_graph

    result = jobcopilot_graph.invoke(
        {"job_text": job_text},
        config={"configurable": {"thread_id": "agent-jobcopilot-pipeline"}},
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
) -> dict[str, Any]:
    """
    Create a Gmail draft for the given recipient, subject, and body.
    """
    return create_gmail_draft(
        to=to,
        subject=subject,
        body=body,
    )


@tool
def create_followup_reminder_tool(
    company: str,
    role: str,
    followup_date: str,
) -> dict[str, Any]:
    """
    Create a Google Calendar follow-up reminder for a job application.
    followup_date must be in YYYY-MM-DD format.
    """
    if has_existing_reminder(
        company=company,
        role=role,
        reminder_date=followup_date,
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

    event_result = create_followup_event(**payload)

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
    """
    Save a job application record locally if it does not already exist.
    """
    existing = find_existing_application(company=company, role=role)

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

    saved = add_application_record(record)

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
    """
    List saved application records.
    """
    return [record.model_dump() for record in load_application_records()]


AGENT_TOOLS = [
    run_jobcopilot_pipeline_tool,
    create_gmail_draft_tool,
    create_followup_reminder_tool,
    save_application_record_tool,
    list_saved_applications_tool,
]