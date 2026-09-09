from __future__ import annotations

import hashlib
from datetime import date, datetime, timezone
from typing import Any
from uuid import uuid4

from app.schemas import (
    ApplicationRecord,
    ApplicationWorkflowEvent,
    ApplicationWorkflowStage,
)
from app.services.applications_store import (
    create_application_record,
    load_application_records,
    save_application_records,
)


STAGE_LABELS: dict[ApplicationWorkflowStage, str] = {
    "discovered": "Discovered",
    "analyzed": "Analyzed",
    "ready_to_apply": "Ready to apply",
    "awaiting_approval": "Awaiting approval",
    "applied": "Applied",
    "follow_up_due": "Follow-up due",
    "interview": "Interview",
    "rejected": "Rejected",
    "offer": "Offer",
    "closed": "Closed",
}

STAGE_ICONS: dict[ApplicationWorkflowStage, str] = {
    "discovered": "○",
    "analyzed": "◇",
    "ready_to_apply": "◈",
    "awaiting_approval": "◷",
    "applied": "✓",
    "follow_up_due": "↗",
    "interview": "◆",
    "rejected": "×",
    "offer": "★",
    "closed": "—",
}

LEGACY_STAGE_MAP: dict[str, ApplicationWorkflowStage] = {
    "drafted": "ready_to_apply",
    "applied": "applied",
    "interview": "interview",
    "follow_up": "follow_up_due",
    "closed": "closed",
}

LEGACY_STATUS_BY_STAGE: dict[ApplicationWorkflowStage, str] = {
    "discovered": "drafted",
    "analyzed": "drafted",
    "ready_to_apply": "drafted",
    "awaiting_approval": "drafted",
    "applied": "applied",
    "follow_up_due": "follow_up",
    "interview": "interview",
    "rejected": "closed",
    "offer": "closed",
    "closed": "closed",
}

VALID_TRANSITIONS: dict[ApplicationWorkflowStage, set[ApplicationWorkflowStage]] = {
    "discovered": {"analyzed", "closed"},
    "analyzed": {"ready_to_apply", "closed"},
    "ready_to_apply": {"awaiting_approval", "closed"},
    "awaiting_approval": {"ready_to_apply", "applied", "closed"},
    "applied": {"follow_up_due", "interview", "rejected", "offer", "closed"},
    "follow_up_due": {"applied", "interview", "rejected", "offer", "closed"},
    "interview": {"follow_up_due", "rejected", "offer", "closed"},
    "rejected": {"closed"},
    "offer": {"closed"},
    "closed": set(),
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize(value: str) -> str:
    return " ".join(str(value).strip().casefold().split())


def _same_application(record: ApplicationRecord, company: str, role: str) -> bool:
    return _normalize(record.company) == _normalize(company) and _normalize(record.role) == _normalize(role)


def _find_index(records: list[ApplicationRecord], company: str, role: str) -> int | None:
    for index, record in enumerate(records):
        if _same_application(record, company, role):
            return index
    return None


def stored_workflow_stage(record: ApplicationRecord) -> ApplicationWorkflowStage:
    """Return the persisted stage, mapping older tracker-only records conservatively."""
    if record.workflow_stage is not None:
        return record.workflow_stage
    return LEGACY_STAGE_MAP.get(record.status, "discovered")


def effective_workflow_stage(
    record: ApplicationRecord,
    *,
    today: date | None = None,
) -> ApplicationWorkflowStage:
    """Expose a due follow-up without requiring a background write at midnight."""
    stage = stored_workflow_stage(record)
    if stage != "applied" or not record.reminder_date:
        return stage
    current_day = today or date.today()
    try:
        reminder = date.fromisoformat(record.reminder_date)
    except ValueError:
        return stage
    return "follow_up_due" if reminder <= current_day else stage


def _event(
    event_type: str,
    stage: ApplicationWorkflowStage,
    *,
    actor: str,
    detail: str = "",
    action_key: str = "",
) -> ApplicationWorkflowEvent:
    return ApplicationWorkflowEvent(
        event_type=event_type,
        stage=stage,
        actor=actor,
        occurred_at=_now_iso(),
        detail=" ".join(str(detail).split()),
        action_key=action_key,
    )


def _with_stage(
    record: ApplicationRecord,
    stage: ApplicationWorkflowStage,
    *,
    event_type: str,
    actor: str,
    detail: str = "",
) -> ApplicationRecord:
    payload = record.model_dump()
    payload["workflow_stage"] = stage
    payload["status"] = LEGACY_STATUS_BY_STAGE[stage]
    payload["updated_at"] = _now_iso()
    history = list(record.workflow_history)
    history.append(_event(event_type, stage, actor=actor, detail=detail))
    payload["workflow_history"] = [item.model_dump() for item in history]
    return ApplicationRecord(**payload)


def create_workflow_application(
    *,
    company: str,
    role: str,
    user_id: str | None,
    stage: ApplicationWorkflowStage = "discovered",
    source: str = "agentic-workflow",
    application_channel: str = "unknown",
    email_subject: str = "",
    email_body: str = "",
    reminder_date: str = "",
    notes: str = "",
    actor: str = "user",
) -> tuple[ApplicationRecord, bool]:
    records = load_application_records(user_id=user_id)
    index = _find_index(records, company, role)
    if index is not None:
        return records[index], False

    record = create_application_record(
        company=company,
        role=role,
        email_subject=email_subject,
        email_body=email_body,
        status=LEGACY_STATUS_BY_STAGE[stage],
        source=source,
        notes=notes,
        reminder_date=reminder_date,
    )
    payload = record.model_dump()
    payload.update(
        {
            "application_id": uuid4().hex,
            "workflow_stage": stage,
            "application_channel": application_channel,
            "updated_at": _now_iso(),
            "workflow_history": [
                _event(
                    "workflow_created",
                    stage,
                    actor=actor,
                    detail=f"Workflow created at stage {STAGE_LABELS[stage]}.",
                ).model_dump()
            ],
        }
    )
    created = ApplicationRecord(**payload)
    records.append(created)
    save_application_records(records, user_id=user_id)
    return created, True


def ensure_ready_application(
    *,
    company: str,
    role: str,
    user_id: str | None,
    application_channel: str = "unknown",
    email_subject: str = "",
    email_body: str = "",
    reminder_date: str = "",
    notes: str = "",
    source: str = "agentic-workflow",
    actor: str = "user",
) -> tuple[ApplicationRecord, bool]:
    """Idempotently persist an analyzed application pack as ready for human review."""
    records = load_application_records(user_id=user_id)
    index = _find_index(records, company, role)
    if index is None:
        record, _ = create_workflow_application(
            company=company,
            role=role,
            user_id=user_id,
            stage="analyzed",
            source=source,
            application_channel=application_channel,
            email_subject=email_subject,
            email_body=email_body,
            reminder_date=reminder_date,
            notes=notes,
            actor=actor,
        )
        return transition_application(
            company,
            role,
            "ready_to_apply",
            user_id=user_id,
            actor=actor,
            event_type="application_pack_ready",
            detail="Grounded application pack reviewed for workflow tracking.",
        ), True

    record = records[index]
    payload = record.model_dump()
    if email_subject:
        payload["email_subject"] = email_subject
    if email_body:
        payload["email_body"] = email_body
    if reminder_date:
        payload["reminder_date"] = reminder_date
    if notes:
        payload["notes"] = notes
    if application_channel:
        payload["application_channel"] = application_channel
    payload["updated_at"] = _now_iso()
    record = ApplicationRecord(**payload)
    records[index] = record
    save_application_records(records, user_id=user_id)

    stage = stored_workflow_stage(record)
    if stage == "discovered":
        record = transition_application(
            company,
            role,
            "analyzed",
            user_id=user_id,
            actor=actor,
            event_type="analysis_completed",
            detail="Offer analysis completed.",
        )
        stage = stored_workflow_stage(record)
    if stage == "analyzed":
        record = transition_application(
            company,
            role,
            "ready_to_apply",
            user_id=user_id,
            actor=actor,
            event_type="application_pack_ready",
            detail="Grounded application pack is ready for human review.",
        )
    return record, False


def transition_application(
    company: str,
    role: str,
    target_stage: ApplicationWorkflowStage,
    *,
    user_id: str | None,
    actor: str = "user",
    event_type: str = "stage_changed",
    detail: str = "",
) -> ApplicationRecord:
    records = load_application_records(user_id=user_id)
    index = _find_index(records, company, role)
    if index is None:
        raise ValueError("Application workflow does not exist.")

    record = records[index]
    current = effective_workflow_stage(record)
    if target_stage == current:
        return record
    if target_stage not in VALID_TRANSITIONS[current]:
        raise ValueError(
            f"Invalid workflow transition: {current} -> {target_stage}."
        )

    updated = _with_stage(
        record,
        target_stage,
        event_type=event_type,
        actor=actor,
        detail=detail or f"Stage changed from {STAGE_LABELS[current]} to {STAGE_LABELS[target_stage]}.",
    )
    records[index] = updated
    save_application_records(records, user_id=user_id)
    return updated


def request_application_approval(
    company: str,
    role: str,
    *,
    user_id: str | None,
    actor: str = "user",
) -> ApplicationRecord:
    return transition_application(
        company,
        role,
        "awaiting_approval",
        user_id=user_id,
        actor=actor,
        event_type="approval_requested",
        detail="Application package frozen for explicit human approval before submission actions.",
    )


def mark_application_applied(
    company: str,
    role: str,
    *,
    user_id: str | None,
    actor: str = "user",
) -> ApplicationRecord:
    return transition_application(
        company,
        role,
        "applied",
        user_id=user_id,
        actor=actor,
        event_type="application_submitted",
        detail="User confirmed that the application was actually submitted or sent.",
    )


def set_application_outcome(
    company: str,
    role: str,
    outcome: ApplicationWorkflowStage,
    *,
    user_id: str | None,
    actor: str = "user",
) -> ApplicationRecord:
    if outcome not in {"interview", "rejected", "offer", "closed"}:
        raise ValueError("Outcome must be interview, rejected, offer or closed.")
    return transition_application(
        company,
        role,
        outcome,
        user_id=user_id,
        actor=actor,
        event_type="application_outcome_updated",
        detail=f"Application outcome updated to {STAGE_LABELS[outcome]}.",
    )


def set_followup_reminder(
    company: str,
    role: str,
    reminder_date: str,
    *,
    user_id: str | None,
    actor: str = "user",
) -> ApplicationRecord:
    parsed = date.fromisoformat(reminder_date)
    records = load_application_records(user_id=user_id)
    index = _find_index(records, company, role)
    if index is None:
        raise ValueError("Application workflow does not exist.")
    record = records[index]
    payload = record.model_dump()
    payload["reminder_date"] = parsed.isoformat()
    payload["updated_at"] = _now_iso()
    stage = effective_workflow_stage(record)
    history = list(record.workflow_history)
    history.append(
        _event(
            "followup_scheduled",
            stage,
            actor=actor,
            detail=f"Follow-up scheduled for {parsed.isoformat()}.",
        )
    )
    payload["workflow_history"] = [item.model_dump() for item in history]
    updated = ApplicationRecord(**payload)
    records[index] = updated
    save_application_records(records, user_id=user_id)
    return updated


def external_action_key(action_type: str, *parts: str) -> str:
    canonical = "|".join([_normalize(action_type), *(_normalize(part) for part in parts)])
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]


def external_action_already_recorded(
    company: str,
    role: str,
    action_key: str,
    *,
    user_id: str | None,
) -> bool:
    records = load_application_records(user_id=user_id)
    index = _find_index(records, company, role)
    if index is None:
        return False
    return action_key in records[index].external_action_keys


def record_external_action(
    company: str,
    role: str,
    *,
    action_type: str,
    action_key: str,
    user_id: str | None,
    detail: str,
    actor: str = "agent",
    reminder_date: str = "",
) -> tuple[ApplicationRecord, bool]:
    """Append one successful side effect once; repeated retries become no-ops."""
    records = load_application_records(user_id=user_id)
    index = _find_index(records, company, role)
    if index is None:
        raise ValueError("Application workflow does not exist.")
    record = records[index]
    if action_key in record.external_action_keys:
        return record, False

    payload = record.model_dump()
    keys = list(record.external_action_keys)
    keys.append(action_key)
    payload["external_action_keys"] = keys
    if reminder_date:
        payload["reminder_date"] = date.fromisoformat(reminder_date).isoformat()
    payload["updated_at"] = _now_iso()
    stage = effective_workflow_stage(record)
    history = list(record.workflow_history)
    history.append(
        _event(
            action_type,
            stage,
            actor=actor,
            detail=detail,
            action_key=action_key,
        )
    )
    payload["workflow_history"] = [item.model_dump() for item in history]
    updated = ApplicationRecord(**payload)
    records[index] = updated
    save_application_records(records, user_id=user_id)
    return updated, True


def next_workflow_actions(record: ApplicationRecord) -> list[str]:
    stage = effective_workflow_stage(record)
    if stage == "discovered":
        return ["Analyze the offer against the verified profile."]
    if stage == "analyzed":
        return ["Build and review the grounded application pack."]
    if stage == "ready_to_apply":
        return ["Review the final materials and request explicit approval."]
    if stage == "awaiting_approval":
        return [
            "Use the confirmed route to prepare external actions if needed.",
            "Mark as applied only after the application is actually submitted or sent.",
        ]
    if stage == "applied":
        return ["Wait for the response and keep the follow-up date current."]
    if stage == "follow_up_due":
        return ["Follow up now, then record any interview, rejection or offer outcome."]
    if stage == "interview":
        return ["Prepare for the interview and record the next outcome or follow-up."]
    if stage == "offer":
        return ["Review the offer and close the workflow when decided."]
    if stage == "rejected":
        return ["Capture useful notes and close the workflow when finished."]
    return []


def workflow_snapshot(record: ApplicationRecord) -> dict[str, Any]:
    stage = effective_workflow_stage(record)
    return {
        "application_id": record.application_id,
        "company": record.company,
        "role": record.role,
        "stage": stage,
        "stage_label": STAGE_LABELS[stage],
        "stage_icon": STAGE_ICONS[stage],
        "application_channel": record.application_channel,
        "reminder_date": record.reminder_date,
        "next_actions": next_workflow_actions(record),
        "history": [event.model_dump() for event in record.workflow_history],
        "external_action_count": len(record.external_action_keys),
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }


def get_workflow_snapshot(
    company: str,
    role: str,
    *,
    user_id: str | None,
) -> dict[str, Any] | None:
    for record in load_application_records(user_id=user_id):
        if _same_application(record, company, role):
            return workflow_snapshot(record)
    return None


def list_workflow_snapshots(user_id: str | None) -> list[dict[str, Any]]:
    return [
        workflow_snapshot(record)
        for record in load_application_records(user_id=user_id)
    ]
