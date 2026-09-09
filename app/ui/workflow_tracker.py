from __future__ import annotations

from datetime import date, timedelta

import streamlit as st

from app.services.application_workflow import (
    STAGE_ICONS,
    STAGE_LABELS,
    effective_workflow_stage,
    mark_application_applied,
    next_workflow_actions,
    request_application_approval,
    set_application_outcome,
    set_followup_reminder,
    transition_application,
)
from app.services.applications_store import (
    load_application_records,
    update_application_record,
)


def _stage_counts(records) -> dict[str, int]:
    counts = {stage: 0 for stage in STAGE_LABELS}
    for record in records:
        counts[effective_workflow_stage(record)] += 1
    return counts


def _render_record_controls(user_id: str, record, index: int) -> None:
    stage = effective_workflow_stage(record)
    st.markdown(
        f"**{STAGE_ICONS[stage]} {STAGE_LABELS[stage]}** · route: `{record.application_channel}`"
    )
    actions = next_workflow_actions(record)
    for action in actions:
        st.write(f"• {action}")

    reminder_default = (
        date.fromisoformat(record.reminder_date)
        if record.reminder_date
        else date.today() + timedelta(days=5)
    )
    reminder = st.date_input(
        "Follow-up date",
        value=reminder_default,
        key=f"workflow-tracker-reminder-{index}-{record.company}-{record.role}",
    )
    notes = st.text_area(
        "Notes",
        value=record.notes,
        key=f"workflow-tracker-notes-{index}-{record.company}-{record.role}",
    )
    save_col, action_col = st.columns(2)
    with save_col:
        if st.button(
            "Save notes & follow-up",
            use_container_width=True,
            key=f"workflow-tracker-save-{index}-{record.company}-{record.role}",
        ):
            set_followup_reminder(
                record.company,
                record.role,
                str(reminder),
                user_id=user_id,
                actor="user",
            )
            update_application_record(
                record.company,
                record.role,
                user_id=user_id,
                notes=notes,
            )
            st.success("Tracker updated.")
            st.rerun()

    with action_col:
        if stage == "ready_to_apply":
            if st.button(
                "Request approval",
                type="primary",
                use_container_width=True,
                key=f"workflow-tracker-approve-{index}-{record.company}-{record.role}",
            ):
                request_application_approval(
                    record.company,
                    record.role,
                    user_id=user_id,
                    actor="user",
                )
                st.rerun()
        elif stage == "awaiting_approval":
            confirmed = st.checkbox(
                "Actually submitted/sent",
                key=f"workflow-tracker-confirm-{index}-{record.company}-{record.role}",
            )
            if st.button(
                "Mark applied",
                type="primary",
                use_container_width=True,
                disabled=not confirmed,
                key=f"workflow-tracker-applied-{index}-{record.company}-{record.role}",
            ):
                mark_application_applied(
                    record.company,
                    record.role,
                    user_id=user_id,
                    actor="user",
                )
                st.rerun()
        elif stage in {"rejected", "offer"}:
            if st.button(
                "Close workflow",
                use_container_width=True,
                key=f"workflow-tracker-close-{index}-{record.company}-{record.role}",
            ):
                transition_application(
                    record.company,
                    record.role,
                    "closed",
                    user_id=user_id,
                    actor="user",
                    event_type="workflow_closed",
                    detail="Workflow closed by the user.",
                )
                st.rerun()

    if stage in {"applied", "follow_up_due", "interview"}:
        st.markdown("**Record a received outcome**")
        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button(
                "Interview",
                use_container_width=True,
                disabled=stage == "interview",
                key=f"workflow-tracker-interview-{index}-{record.company}-{record.role}",
            ):
                set_application_outcome(
                    record.company,
                    record.role,
                    "interview",
                    user_id=user_id,
                    actor="user",
                )
                st.rerun()
        with c2:
            if st.button(
                "Rejected",
                use_container_width=True,
                key=f"workflow-tracker-rejected-{index}-{record.company}-{record.role}",
            ):
                set_application_outcome(
                    record.company,
                    record.role,
                    "rejected",
                    user_id=user_id,
                    actor="user",
                )
                st.rerun()
        with c3:
            if st.button(
                "Offer",
                use_container_width=True,
                key=f"workflow-tracker-offer-{index}-{record.company}-{record.role}",
            ):
                set_application_outcome(
                    record.company,
                    record.role,
                    "offer",
                    user_id=user_id,
                    actor="user",
                )
                st.rerun()

    if record.workflow_history:
        with st.expander("Audit trail"):
            for event in reversed(record.workflow_history):
                st.write(
                    f"**{event.occurred_at[:19]} · {STAGE_LABELS[event.stage]}** — {event.detail or event.event_type}"
                )
                st.caption(
                    f"{event.actor} · {event.event_type}"
                    + (f" · action {event.action_key[:8]}…" if event.action_key else "")
                )
    else:
        st.caption(
            "Legacy tracker record: lifecycle is inferred from the previous status until the next workflow mutation."
        )


def render_workflow_tracker(user_id: str) -> None:
    st.markdown("## Application workflow")
    st.caption(
        "A deterministic state machine tracks what is prepared, approved, actually submitted and due for follow-up."
    )
    records = load_application_records(user_id=user_id)
    if not records:
        st.info("No application saved yet. Analyze an offer and choose Track as ready to apply.")
        return

    counts = _stage_counts(records)
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Tracked", len(records))
    k2.metric("Awaiting approval", counts["awaiting_approval"])
    k3.metric("Applied", counts["applied"])
    k4.metric("Follow-up due", counts["follow_up_due"])

    filter_col, search_col = st.columns([1, 2])
    with filter_col:
        stage_filter = st.selectbox(
            "Workflow stage",
            ["All", *[STAGE_LABELS[stage] for stage in STAGE_LABELS]],
            key="workflow-stage-filter",
        )
    with search_col:
        query = st.text_input(
            "Search",
            placeholder="Company or role",
            key="workflow-search",
        )

    filtered = []
    for record in records:
        stage = effective_workflow_stage(record)
        if stage_filter != "All" and STAGE_LABELS[stage] != stage_filter:
            continue
        if query.strip() and query.casefold() not in f"{record.company} {record.role}".casefold():
            continue
        filtered.append(record)

    rows = []
    for record in reversed(filtered):
        stage = effective_workflow_stage(record)
        rows.append(
            {
                "Company": record.company,
                "Role": record.role,
                "Stage": f"{STAGE_ICONS[stage]} {STAGE_LABELS[stage]}",
                "Route": record.application_channel,
                "Follow-up": record.reminder_date or "—",
                "External actions": len(record.external_action_keys),
            }
        )
    st.dataframe(rows, use_container_width=True, hide_index=True)

    st.markdown("### Manage lifecycle")
    for index, record in enumerate(reversed(filtered)):
        stage = effective_workflow_stage(record)
        with st.expander(
            f"{record.company} — {record.role} · {STAGE_LABELS[stage]}"
        ):
            _render_record_controls(user_id, record, index)
