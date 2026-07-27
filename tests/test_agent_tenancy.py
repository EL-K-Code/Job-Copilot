from __future__ import annotations

from types import SimpleNamespace

from app import agent_graph, agent_tools
from app.schemas import ApplicationRecord


def _tool_map(user_id: str):
    return {tool.name: tool for tool in agent_tools.build_agent_tools(user_id)}


def test_bound_agent_tools_do_not_expose_user_id_to_model():
    tools = _tool_map("alice")

    assert tools
    for current_tool in tools.values():
        assert "user_id" not in current_tool.args


def test_pipeline_tool_forwards_bound_user_to_retrieval_graph(monkeypatch):
    captured = {}

    class FakeGraph:
        def invoke(self, state, config=None):
            captured["state"] = state
            captured["config"] = config
            return {
                "job_analysis": {
                    "company": "Example",
                    "role": "ML Engineer",
                    "application_channel": "ats_portal",
                },
                "retrieved_memories": ["Alice works with Python."],
                "match_insight": {"strengths": [], "gaps": [], "suggested_angles": []},
                "application_pack": {
                    "channel": "ats_portal",
                    "route_label": "Portal or ATS application",
                },
                "email_draft": {"subject": "Application", "body": "Hello"},
            }

    monkeypatch.setattr("app.graph.jobcopilot_graph", FakeGraph())
    result = _tool_map("alice")["run_jobcopilot_pipeline_tool"].invoke(
        {"job_text": "A complete job offer"}
    )

    assert captured["state"]["user_id"] == "alice"
    assert captured["state"]["job_text"] == "A complete job offer"
    assert "alice" in captured["config"]["configurable"]["thread_id"]
    assert result["job_analysis"]["company"] == "Example"
    assert result["application_pack"]["channel"] == "ats_portal"


def test_gmail_tool_uses_only_bound_users_google_token(monkeypatch):
    calls = []

    def fake_create_gmail_draft(**kwargs):
        calls.append(kwargs)
        return {"draft_id": "draft-1"}

    monkeypatch.setattr(agent_tools, "create_gmail_draft", fake_create_gmail_draft)
    gmail_tool = _tool_map("alice")["create_gmail_draft_tool"]

    preview = gmail_tool.invoke(
        {
            "to": "recruiter@example.com",
            "subject": "Application",
            "body": "Hello",
            "confirmed": False,
        }
    )
    assert preview["status"] == "confirmation_required"
    assert calls == []

    created = gmail_tool.invoke(
        {
            "to": "recruiter@example.com",
            "subject": "Application",
            "body": "Hello",
            "confirmed": True,
        }
    )
    assert created["status"] == "created"
    assert calls == [
        {
            "to": "recruiter@example.com",
            "subject": "Application",
            "body": "Hello",
            "user_id": "alice",
        }
    ]


def test_application_agent_tools_never_cross_user_boundaries(monkeypatch):
    captured = {"lookups": [], "writes": [], "lists": []}

    def fake_find(company, role, user_id=None):
        captured["lookups"].append((company, role, user_id))
        return None

    def fake_add(record, user_id=None):
        captured["writes"].append((record.company, user_id))
        return True

    def fake_load(user_id=None):
        captured["lists"].append(user_id)
        return [ApplicationRecord(company=f"{user_id.title()} Labs", role="Engineer")]

    monkeypatch.setattr(agent_tools, "find_existing_application", fake_find)
    monkeypatch.setattr(agent_tools, "add_application_record", fake_add)
    monkeypatch.setattr(agent_tools, "load_application_records", fake_load)

    alice_tools = _tool_map("alice")
    save_result = alice_tools["save_application_record_tool"].invoke(
        {"company": "Alice Labs", "role": "Engineer"}
    )
    listed = alice_tools["list_saved_applications_tool"].invoke({})

    assert save_result["status"] == "saved"
    assert captured["lookups"] == [("Alice Labs", "Engineer", "alice")]
    assert captured["writes"] == [("Alice Labs", "alice")]
    assert captured["lists"] == ["alice"]
    assert listed[0]["company"] == "Alice Labs"


def test_calendar_tool_uses_bound_user_for_duplicate_check_and_event(monkeypatch):
    captured = {}

    def fake_has_existing_reminder(**kwargs):
        captured["duplicate_check"] = kwargs
        return False

    def fake_create_followup_event(**kwargs):
        captured["event"] = kwargs
        return {"event_id": "event-1"}

    monkeypatch.setattr(
        agent_tools,
        "has_existing_reminder",
        fake_has_existing_reminder,
    )
    monkeypatch.setattr(
        agent_tools,
        "create_followup_event",
        fake_create_followup_event,
    )

    result = _tool_map("bob")["create_followup_reminder_tool"].invoke(
        {
            "company": "Bob Systems",
            "role": "Data Engineer",
            "followup_date": "2026-08-01",
            "confirmed": True,
        }
    )

    assert result["status"] == "created"
    assert captured["duplicate_check"]["user_id"] == "bob"
    assert captured["event"]["user_id"] == "bob"


def test_each_user_gets_a_distinct_agent_graph_and_checkpointer():
    agent_graph.clear_jobcopilot_agent_graph_cache()

    alice_first = agent_graph.get_jobcopilot_agent_graph("alice")
    alice_second = agent_graph.get_jobcopilot_agent_graph("alice")
    bob = agent_graph.get_jobcopilot_agent_graph("bob")

    assert alice_first is alice_second
    assert alice_first is not bob
