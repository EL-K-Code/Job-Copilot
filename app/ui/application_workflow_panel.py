from __future__ import annotations

from datetime import date, timedelta
from html import escape

import streamlit as st

from app.services.application_workflow import (
    STAGE_ICONS,
    STAGE_LABELS,
    effective_workflow_stage,
    ensure_ready_application,
    mark_application_applied,
    next_workflow_actions,
    request_application_approval,
    set_application_outcome,
    set_followup_reminder,
)
from app.services.applications_store import find_existing_application


_STAGE_ORDER = [
    "discovered",
    "analyzed",
    "ready_to_apply",
    "awaiting_approval",
    "applied",
    "follow_up_due",
    "interview",
    "offer",
]


def _render_stage_path(current_stage: str) -> None:
    display = [
        "analyzed",
        "ready_to_apply",
        "awaiting_approval",
        "applied",
        "follow_up_due",
        "interview",
        "offer",
    ]
    current_index = _STAGE_ORDER.index(current_stage) if current_stage in _STAGE_ORDER else -1
    columns = st.columns(len(display))
    for index, stage in enumerate(display):
        reached = current_index >= _STAGE_ORDER.index(stage)
        marker = "✓" if reached else "·"
        columns[index].markdown(
            f"**{marker} {STAGE_LABELS[stage]}**" if stage == current_stage else f"{marker} {STAGE_LABELS[stage]}"
        )


def _safe_editor_value(key: str, fallback: str) -> str:
    value = st.session_state.get(key)
    return str(value) if isinstance(value, str) else fallback


def render_application_workflow_panel(user: dict[str, str]) -> None:
    """Render the deterministic, human-supervised lifecycle for the current analyzed offer."""
    results = st.session_state.get("results")
    if not isinstance(results, dict):
        return

    analysis = dict(results.get("job_analysis", {}) or {})
    draft = dict(results.get("email_draft", {}) or {})
    company = str(analysis.get("company", "")).strip()
    role = str(analysis.get("role", "")).strip()
    if not company or not role or company == "Unknown" or role == "Unknown":
        return

    user_id = user["user_id"]
    record = find_existing_application(company, role, user_id=user_id)

    st.divider()
    st.markdown("## Supervised application workflow")
    st.caption(
        "The LLM may analyze and prepare materials, but lifecycle changes and external actions remain deterministic and human-controlled."
    )

    if record is None:
        with st.container(border=True):
            st.markdown("### Start tracking this application")
            st.write(
                "The analysis stays read-only until you choose to track it. Saving creates a Ready to apply workflow; it does not submit anything."
            )
            if st.button(
                "Track as ready to apply",
                type="primary",
                use_container_width=True,
                key="workflow-track-current",
            ):
                reminder = st.session_state.get("beta_followup_date")
                reminder_date = str(reminder) if reminder else ""
                created, _ = ensure_ready_application(
                    company=company,
                    role=role,
                    user_id=user_id,
                    application_channel=str(analysis.get("application_channel", "unknown")),
                    email_subject=_safe_editor_value(
                        "beta_email_subject", str(draft.get("subject", ""))
                    ),
                    email_body=_safe_editor_value(
                        "beta_email_body", str(draft.get("body", ""))
                    ),
                    reminder_date=reminder_date,
                    notes="Created from an evidence-grounded JobCopilot analysis.",
                    source="private-beta-agentic",
                    actor="user",
                )
                st.success(
                    f"Tracked at {STAGE_LABELS[effective_workflow_stage(created)]}. No application was submitted."
                )
                st.rerun()
        return

    stage = effective_workflow_stage(record)
    st.markdown(
        f"""
        <div class="jc-card">
          <div class="jc-eyebrow">Current lifecycle stage</div>
          <div class="jc-card-title" style="font-size:1.25rem">{escape(STAGE_ICONS[stage])} {escape(STAGE_LABELS[stage])}</div>
          <div class="jc-muted">{escape(record.company)} · {escape(record.role)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    _render_stage_path(stage)

    next_actions = next_workflow_actions(record)
    if next_actions:
        st.markdown("#### Recommended next action")
        for item in next_actions:
            st.write(f"• {item}")

    if stage == "ready_to_apply":
        with st.container(border=True):
            st.markdown("### Human approval gate")
            st.write(
                "Requesting approval freezes the workflow at Awaiting approval. It still does not send Gmail, submit an ATS form or create a Calendar event."
            )
            if st.button(
                "Move to awaiting approval",
                type="primary",
                use_container_width=True,
                key="workflow-request-approval",
            ):
                request_application_approval(
                    company,
                    role,
                    user_id=user_id,
                    actor="user",
                )
                st.success("Awaiting your explicit approval before the application can be marked as submitted.")
                st.rerun()

    elif stage == "awaiting_approval":
        with st.container(border=True):
            st.markdown("### Confirm actual submission")
            confirmed = st.checkbox(
                "I confirm that I actually submitted or sent this application.",
                key="workflow-confirm-applied",
            )
            if st.button(
                "Mark as applied",
                type="primary",
                use_container_width=True,
                disabled=not confirmed,
                key="workflow-mark-applied",
            ):
                mark_application_applied(
                    company,
                    role,
                    user_id=user_id,
                    actor="user",
                )
                st.success("Application marked as applied from your explicit confirmation.")
                st.rerun()

    elif stage in {"applied", "follow_up_due", "interview"}:
        with st.container(border=True):
            st.markdown("### Follow-up and outcome")
            current_reminder = (
                date.fromisoformat(record.reminder_date)
                if record.reminder_date
                else date.today() + timedelta(days=5)
            )
            followup = st.date_input(
                "Follow-up date",
                value=max(current_reminder, date.today()) if stage != "follow_up_due" else current_reminder,
                key="workflow-followup-date",
            )
            if st.button(
                "Save follow-up date",
                use_container_width=True,
                key="workflow-save-followup",
            ):
                set_followup_reminder(
                    company,
                    role,
                    str(followup),
                    user_id=user_id,
                    actor="user",
                )
                st.success("Follow-up date saved.")
                st.rerun()

            st.markdown("**Record only an outcome you actually received:**")
            interview_col, rejected_col, offer_col = st.columns(3)
            with interview_col:
                if st.button(
                    "Interview",
                    use_container_width=True,
                    disabled=stage == "interview",
                    key="workflow-outcome-interview",
                ):
                    set_application_outcome(
                        company,
                        role,
                        "interview",
                        user_id=user_id,
                        actor="user",
                    )
                    st.rerun()
            with rejected_col:
                if st.button(
                    "Rejected",
                    use_container_width=True,
                    key="workflow-outcome-rejected",
                ):
                    set_application_outcome(
                        company,
                        role,
                        "rejected",
                        user_id=user_id,
                        actor="user",
                    )
                    st.rerun()
            with offer_col:
                if st.button(
                    "Offer",
                    use_container_width=True,
                    key="workflow-outcome-offer",
                ):
                    set_application_outcome(
                        company,
                        role,
                        "offer",
                        user_id=user_id,
                        actor="user",
                    )
                    st.rerun()

    if record.workflow_history:
        with st.expander("Workflow audit trail"):
            for event in reversed(record.workflow_history):
                st.write(
                    f"**{event.occurred_at[:19]} · {STAGE_LABELS[event.stage]}** — {event.detail or event.event_type}"
                )
                st.caption(f"Actor: {event.actor} · Event: {event.event_type}")
