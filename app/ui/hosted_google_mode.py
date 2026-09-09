from __future__ import annotations

from datetime import date, datetime, timedelta
from html import escape

import streamlit as st

from app.config import settings
from app.services.applications_store import load_application_records
from app.services.google_oauth import (
    build_google_authorization_url,
    disconnect_hosted_google,
    hosted_google_token_exists,
)
from app.services.profile_store import delete_user_data, export_user_data
from app.tenancy import get_user_paths
from app.ui import premium_private_beta as premium


def _parse_date(value: str) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def render_overview(user: dict[str, str]) -> None:
    user_id = user["user_id"]
    records = load_application_records(user_id=user_id)
    today = date.today()
    upcoming = []
    for record in records:
        reminder = _parse_date(record.reminder_date)
        if reminder is not None and today <= reminder <= today + timedelta(days=7):
            upcoming.append(record)

    active = [record for record in records if record.status != "closed"]
    interviews = [record for record in records if record.status == "interview"]
    connected = hosted_google_token_exists(user_id)

    st.markdown(
        f"""
        <div class="jc-hero">
          <div class="jc-eyebrow">Hosted recruiter demo</div>
          <h1>Welcome, {escape(user['display_name'])}</h1>
          <p>Analyze a role, inspect grounded evidence, build an application pack and optionally create reviewed Gmail drafts or Calendar follow-ups.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Applications", len(records))
    c2.metric("Active", len(active))
    c3.metric("Interviews", len(interviews))
    c4.metric("Due this week", len(upcoming))

    st.markdown("### Try the product")
    q1, q2, q3 = st.columns(3)
    with q1:
        st.markdown(
            '<div class="jc-card"><div class="jc-card-title">Analyze an opportunity</div><p class="jc-muted">Paste a job offer and build an evidence-grounded application pack.</p></div>',
            unsafe_allow_html=True,
        )
        if st.button("Start an application", type="primary", use_container_width=True):
            premium._request_navigation("New application")
    with q2:
        st.markdown(
            '<div class="jc-card"><div class="jc-card-title">Work with Agent Chat</div><p class="jc-muted">Inspect role fit, saved applications and confirmed external actions.</p></div>',
            unsafe_allow_html=True,
        )
        if st.button("Open Agent Chat", use_container_width=True):
            premium._request_navigation("Agent Chat")
    with q3:
        status = "Connected" if connected else "Not connected"
        st.markdown(
            f'<div class="jc-card"><div class="jc-card-title">Google Workspace</div><p class="jc-muted">Status: <strong>{status}</strong>. OAuth tokens are encrypted before persistent storage.</p></div>',
            unsafe_allow_html=True,
        )
        if st.button("Manage Google connection", use_container_width=True):
            premium._request_navigation("Settings")

    left, right = st.columns([1.7, 1])
    with left:
        st.markdown("### Recent applications")
        if not records:
            st.info("The tracker is empty. Start with one opportunity to test persistence.")
        else:
            rows = [
                {
                    "Company": record.company,
                    "Role": record.role,
                    "Status": premium.STATUS_LABELS[record.status],
                    "Reminder": record.reminder_date or "—",
                }
                for record in reversed(records[-6:])
            ]
            st.dataframe(rows, use_container_width=True, hide_index=True)
    with right:
        st.markdown("### Trust boundary")
        model = settings.openai_model if settings.llm_provider == "openai" else settings.anthropic_model
        st.markdown(
            f"""
            <div class="jc-card">
              <div class="jc-card-title">Evidence before persuasion</div>
              <p class="jc-muted">Provider: <strong>{escape(settings.llm_provider.title())}</strong></p>
              <p class="jc-muted">Model: {escape(model)}</p>
              <p class="jc-muted">Gmail drafts and Calendar events remain confirmation-gated and use the authenticated tester's own Google account.</p>
              <span class="jc-pill jc-pill-success">Supabase durable</span>
              <span class="jc-pill">OAuth encrypted</span>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_settings(user_id: str) -> None:
    paths = get_user_paths(user_id)
    connected = hosted_google_token_exists(user_id)
    flash = st.session_state.pop("google_oauth_flash", None)

    st.markdown("## Settings & privacy")
    if flash:
        st.success(flash)

    c1, c2 = st.columns(2)
    with c1:
        with st.container(border=True):
            st.markdown("### Google Workspace")
            st.write(f"Connection status: **{'Connected' if connected else 'Not connected'}**")
            st.caption(
                "JobCopilot requests only Gmail compose and Calendar event access. "
                "OAuth credentials are encrypted before being stored in server-only Supabase state."
            )
            if connected:
                if st.button("Disconnect Google", use_container_width=True):
                    disconnect_hosted_google(user_id)
                    from app.agent_graph import clear_jobcopilot_agent_graph_cache

                    clear_jobcopilot_agent_graph_cache()
                    st.success("Google disconnected. Stored OAuth credentials were deleted.")
                    st.rerun()
            else:
                authorization_url = build_google_authorization_url(user_id)
                st.link_button(
                    "Connect Google securely",
                    authorization_url,
                    type="primary",
                    use_container_width=True,
                )
    with c2:
        with st.container(border=True):
            st.markdown("### AI transparency")
            st.write(f"Primary provider: **{settings.llm_provider.title()}**")
            fallback = settings.llm_fallback_provider.title() if settings.llm_fallback_provider else "Disabled"
            st.write(f"Fallback: **{fallback}**")
            st.caption(
                "Google external actions still require explicit confirmation. Provider telemetry never stores prompts, generated content, API keys or OAuth tokens."
            )

    with st.container(border=True):
        st.markdown("### Your data")
        st.caption(f"Temporary runtime workspace: {paths.root}")
        export_bytes = export_user_data(user_id)
        st.download_button(
            "Export my profile and applications",
            data=export_bytes,
            file_name=f"jobcopilot-{user_id}-export.zip",
            mime="application/zip",
            use_container_width=True,
        )
        st.caption("OAuth tokens are intentionally excluded from exports.")

    with st.expander("Danger zone"):
        st.warning(
            "Deleting application data removes the verified profile, tracker state, quota ledger and stored Google OAuth credentials. The private-beta login is preserved."
        )
        confirmation = st.text_input("Type DELETE to confirm", key="hosted_google_delete_confirmation")
        if st.button("Delete my application data", use_container_width=True):
            if confirmation != "DELETE":
                st.warning("Type DELETE exactly before continuing.")
            else:
                delete_user_data(user_id)
                st.session_state.pop("results", None)
                premium._reset_agent_chat(user_id)
                st.success("Application data and Google OAuth credentials were deleted.")
                st.rerun()
