from app import agent_tools
from app.agent_tools import (
    create_followup_reminder_tool,
    create_gmail_draft_tool,
)


def _tool_map(tools):
    return {tool.name: tool for tool in tools}


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


def test_mark_applied_tool_requires_explicit_confirmation(monkeypatch):
    monkeypatch.setattr(
        agent_tools,
        "get_workflow_snapshot",
        lambda company, role, user_id=None: {
            "company": company,
            "role": role,
            "stage": "awaiting_approval",
        },
    )
    tools = _tool_map(agent_tools.build_agent_tools("alex", include_google=False))

    result = tools["mark_application_applied_tool"].invoke(
        {
            "company": "Example Labs",
            "role": "ML Engineer",
            "confirmed": False,
        }
    )

    assert result["status"] == "confirmation_required"
    assert result["preview"]["current_stage"] == "awaiting_approval"
    assert result["preview"]["target_stage"] == "applied"


def test_outcome_tool_requires_explicit_confirmation(monkeypatch):
    called = False

    def fail_if_called(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("Outcome mutation must not run before confirmation.")

    monkeypatch.setattr(agent_tools, "set_application_outcome", fail_if_called)
    tools = _tool_map(agent_tools.build_agent_tools("alex", include_google=False))

    result = tools["update_application_outcome_tool"].invoke(
        {
            "company": "Example Labs",
            "role": "ML Engineer",
            "outcome": "offer",
            "confirmed": False,
        }
    )

    assert result["status"] == "confirmation_required"
    assert result["preview"]["outcome"] == "offer"
    assert called is False
