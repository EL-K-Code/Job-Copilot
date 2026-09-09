from __future__ import annotations

from types import SimpleNamespace

from app import agent_graph, agent_tools


def _tool_names(tools) -> set[str]:
    return {tool.name for tool in tools}


def test_hosted_recruiter_demo_excludes_google_agent_tools(monkeypatch):
    monkeypatch.setattr(
        agent_tools,
        "settings",
        SimpleNamespace(hosted_recruiter_demo=True),
    )

    names = _tool_names(agent_tools.build_agent_tools("recruiter-demo"))

    assert names == {
        "run_jobcopilot_pipeline_tool",
        "save_application_record_tool",
        "get_application_workflow_tool",
        "prepare_application_for_approval_tool",
        "mark_application_applied_tool",
        "update_application_outcome_tool",
        "list_saved_applications_tool",
    }
    assert "create_gmail_draft_tool" not in names
    assert "create_followup_reminder_tool" not in names


def test_local_private_beta_keeps_google_agent_tools(monkeypatch):
    monkeypatch.setattr(
        agent_tools,
        "settings",
        SimpleNamespace(hosted_recruiter_demo=False),
    )

    names = _tool_names(agent_tools.build_agent_tools("alex"))

    assert {
        "create_gmail_draft_tool",
        "create_followup_reminder_tool",
    }.issubset(names)


def test_explicit_legacy_tool_build_can_include_google(monkeypatch):
    monkeypatch.setattr(
        agent_tools,
        "settings",
        SimpleNamespace(hosted_recruiter_demo=True),
    )

    names = _tool_names(
        agent_tools.build_agent_tools("recruiter-demo", include_google=True)
    )

    assert "create_gmail_draft_tool" in names
    assert "create_followup_reminder_tool" in names


def test_hosted_agent_prompt_states_google_boundary(monkeypatch):
    monkeypatch.setattr(
        agent_graph,
        "settings",
        SimpleNamespace(hosted_recruiter_demo=True),
    )

    prompt = agent_graph._system_prompt()

    assert "Gmail and Google Calendar actions are intentionally unavailable" in prompt
    assert "Do not claim that you can connect Google" in prompt


def test_local_agent_prompt_keeps_confirmation_rules(monkeypatch):
    monkeypatch.setattr(
        agent_graph,
        "settings",
        SimpleNamespace(hosted_recruiter_demo=False),
    )

    prompt = agent_graph._system_prompt()

    assert "Never create a Gmail draft or Calendar event without explicit confirmation" in prompt
