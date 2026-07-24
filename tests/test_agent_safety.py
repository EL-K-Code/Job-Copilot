from app.agent_tools import (
    create_followup_reminder_tool,
    create_gmail_draft_tool,
)


def test_gmail_tool_requires_explicit_confirmation():
    result = create_gmail_draft_tool.invoke(
        {
            "to": "recruiter@example.com",
            "subject": "Application",
            "body": "Hello",
            "confirmed": False,
        }
    )

    assert result["status"] == "confirmation_required"
    assert result["preview"]["to"] == "recruiter@example.com"


def test_calendar_tool_requires_explicit_confirmation():
    result = create_followup_reminder_tool.invoke(
        {
            "company": "Example Labs",
            "role": "ML Engineer",
            "followup_date": "2026-08-15",
            "confirmed": False,
        }
    )

    assert result["status"] == "confirmation_required"
    assert result["preview"]["company"] == "Example Labs"
