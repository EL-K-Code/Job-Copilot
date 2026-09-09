from __future__ import annotations

from datetime import date

import pytest

from app.schemas import ApplicationRecord
from app.services import application_workflow as workflow


def _in_memory_store(monkeypatch):
    state: list[ApplicationRecord] = []

    def load_application_records(user_id=None):
        return list(state)

    def save_application_records(records, user_id=None):
        state[:] = list(records)

    monkeypatch.setattr(workflow, "load_application_records", load_application_records)
    monkeypatch.setattr(workflow, "save_application_records", save_application_records)
    return state


def test_ready_approval_applied_lifecycle_requires_explicit_gate(monkeypatch):
    state = _in_memory_store(monkeypatch)

    record, created = workflow.ensure_ready_application(
        company="Example AI",
        role="ML Engineer",
        user_id="alice",
        application_channel="ats_portal",
        email_subject="Application",
        email_body="Grounded draft",
        actor="user",
    )

    assert created is True
    assert workflow.stored_workflow_stage(record) == "ready_to_apply"
    assert state[0].application_id
    assert state[0].application_channel == "ats_portal"

    with pytest.raises(ValueError, match="Invalid workflow transition"):
        workflow.mark_application_applied(
            "Example AI",
            "ML Engineer",
            user_id="alice",
            actor="user",
        )

    awaiting = workflow.request_application_approval(
        "Example AI",
        "ML Engineer",
        user_id="alice",
        actor="user",
    )
    assert awaiting.workflow_stage == "awaiting_approval"

    applied = workflow.mark_application_applied(
        "Example AI",
        "ML Engineer",
        user_id="alice",
        actor="user",
    )
    assert applied.workflow_stage == "applied"
    assert applied.status == "applied"
    assert [event.event_type for event in applied.workflow_history][-2:] == [
        "approval_requested",
        "application_submitted",
    ]


def test_followup_due_is_derived_without_background_mutation(monkeypatch):
    _in_memory_store(monkeypatch)
    workflow.ensure_ready_application(
        company="Example",
        role="Engineer",
        user_id="alice",
    )
    workflow.request_application_approval("Example", "Engineer", user_id="alice")
    applied = workflow.mark_application_applied("Example", "Engineer", user_id="alice")
    assert workflow.effective_workflow_stage(applied, today=date(2026, 9, 9)) == "applied"

    reminded = workflow.set_followup_reminder(
        "Example",
        "Engineer",
        "2026-09-08",
        user_id="alice",
    )
    assert reminded.workflow_stage == "applied"
    assert workflow.effective_workflow_stage(reminded, today=date(2026, 9, 9)) == "follow_up_due"


def test_external_action_audit_is_idempotent(monkeypatch):
    _in_memory_store(monkeypatch)
    workflow.ensure_ready_application(
        company="Example",
        role="Engineer",
        user_id="alice",
    )
    key = workflow.external_action_key(
        "gmail_draft_created",
        "Example",
        "Engineer",
        "recruiter@example.com",
        "Application",
        "Hello",
    )

    first, appended = workflow.record_external_action(
        "Example",
        "Engineer",
        action_type="gmail_draft_created",
        action_key=key,
        user_id="alice",
        detail="Gmail draft created for recruiter@example.com.",
    )
    second, appended_again = workflow.record_external_action(
        "Example",
        "Engineer",
        action_type="gmail_draft_created",
        action_key=key,
        user_id="alice",
        detail="Retry",
    )

    assert appended is True
    assert appended_again is False
    assert first.external_action_keys == [key]
    assert second.external_action_keys == [key]
    matching_events = [
        event for event in second.workflow_history if event.action_key == key
    ]
    assert len(matching_events) == 1


def test_legacy_records_map_to_new_workflow_stages():
    assert workflow.stored_workflow_stage(
        ApplicationRecord(company="A", role="R", status="drafted")
    ) == "ready_to_apply"
    assert workflow.stored_workflow_stage(
        ApplicationRecord(company="A", role="R", status="follow_up")
    ) == "follow_up_due"
    assert workflow.stored_workflow_stage(
        ApplicationRecord(company="A", role="R", status="interview")
    ) == "interview"


def test_user_reported_outcomes_follow_valid_transition_graph(monkeypatch):
    _in_memory_store(monkeypatch)
    workflow.ensure_ready_application(
        company="Example",
        role="Engineer",
        user_id="alice",
    )
    workflow.request_application_approval("Example", "Engineer", user_id="alice")
    workflow.mark_application_applied("Example", "Engineer", user_id="alice")

    interview = workflow.set_application_outcome(
        "Example",
        "Engineer",
        "interview",
        user_id="alice",
    )
    assert interview.workflow_stage == "interview"

    offer = workflow.set_application_outcome(
        "Example",
        "Engineer",
        "offer",
        user_id="alice",
    )
    assert offer.workflow_stage == "offer"
    assert offer.status == "closed"

    closed = workflow.transition_application(
        "Example",
        "Engineer",
        "closed",
        user_id="alice",
    )
    assert closed.workflow_stage == "closed"
