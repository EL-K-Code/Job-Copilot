from __future__ import annotations

from datetime import date, datetime, timedelta
from html import escape

import streamlit as st
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.config import settings
from app.services.applications_store import (
    add_application_record,
    create_application_record,
    find_existing_application,
    load_application_records,
)
from app.services.profile_store import delete_user_data, export_user_data
from app.services.usage_quota import UsageQuotaExceeded
from app.tenancy import get_user_paths
from app.ui import application_workspace as application
from app.ui import premium_private_beta as premium
from app.ui.application_pack_panel import render_application_pack


def _parse_date(value: str) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def render_overview(user: dict[str, str]) -> None:
    """Render a recruiter-facing overview without unavailable hosted integrations."""
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

    st.markdown(
        f"""
        <div class="jc-hero">
          <div class="jc-eyebrow">Hosted recruiter demo</div>
          <h1>Welcome, {escape(user['display_name'])}</h1>
          <p>Analyze a role, inspect the exact profile evidence behind each claim, build a channel-aware application pack and keep the workflow persistent across sessions.</p>
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
        if st.button(
            "Start an application",
            type="primary",
            use_container_width=True,
            key="hosted-start-application",
        ):
            premium._request_navigation("New application")
    with q2:
        st.markdown(
            '<div class="jc-card"><div class="jc-card-title">Inspect Agent Chat</div><p class="jc-muted">Ask about saved applications, role fit or the grounding architecture.</p></div>',
            unsafe_allow_html=True,
        )
        if st.button(
            "Open Agent Chat",
            use_container_width=True,
            key="hosted-open-agent",
        ):
            premium._request_navigation("Agent Chat")
    with q3:
        st.markdown(
            '<div class="jc-card"><div class="jc-card-title">Durable private beta</div><p class="jc-muted">Profiles, tracker state and quotas persist in Supabase; raw CV files are not stored.</p></div>',
            unsafe_allow_html=True,
        )
        if st.button(
            "View privacy settings",
            use_container_width=True,
            key="hosted-open-settings",
        ):
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
        model = (
            settings.openai_model
            if settings.llm_provider == "openai"
            else settings.anthropic_model
        )
        st.markdown(
            f"""
            <div class="jc-card">
              <div class="jc-card-title">Evidence before persuasion</div>
              <p class="jc-muted">Provider: <strong>{escape(settings.llm_provider.title())}</strong></p>
              <p class="jc-muted">Model: {escape(model)}</p>
              <p class="jc-muted">Candidate claims must resolve to verified memory IDs. Unsupported strengthening is rejected.</p>
              <span class="jc-pill jc-pill-success">Supabase durable</span>
              <span class="jc-pill">Google actions off</span>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _render_hosted_email_actions(user_id: str, analysis: dict, draft: dict) -> None:
    """Keep editing and tracker persistence while removing hosted Google actions."""
    application._sync_email_editor(draft, analysis)
    channel = str(analysis.get("application_channel", "unknown"))
    if channel != "email":
        st.info(
            "The detected application route does not explicitly require email. This draft is "
            "kept as an optional outreach or fallback format."
        )

    st.markdown(
        '<div class="jc-step">Optional · Review the email</div>',
        unsafe_allow_html=True,
    )
    subject = st.text_input("Subject", key="beta_email_subject")
    body = st.text_area("Email body", height=360, key="beta_email_body")

    st.info(
        "Hosted recruiter demo: Gmail and Google Calendar actions are intentionally disabled. "
        "The generated content and application tracker remain fully testable."
    )

    followup_date = st.date_input(
        "Internal follow-up date",
        value=date.today() + timedelta(days=5),
        min_value=date.today(),
        key="hosted_followup_date",
    )

    if st.button(
        "Save application to persistent tracker",
        type="primary",
        use_container_width=True,
        key="hosted_save_tracker",
    ):
        company = str(analysis.get("company", ""))
        role = str(analysis.get("role", ""))
        existing = find_existing_application(company, role, user_id=user_id)
        if existing:
            st.warning("This application already exists in your tracker.")
            return

        record = create_application_record(
            company=company,
            role=role,
            email_subject=subject,
            email_body=body,
            source="hosted-recruiter-demo",
            reminder_date=str(followup_date),
            notes=(
                "Hosted recruiter demo. Recommended application route: "
                f"{channel}. External Google actions disabled."
            ),
        )
        add_application_record(record, user_id=user_id)
        st.success("Saved. This tracker state is durable across sessions.")


def render_application_workspace(user: dict[str, str]) -> None:
    """Render the complete offer workflow with safe hosted-demo actions."""
    user_id = user["user_id"]
    candidate_name = str(user.get("display_name", "")).strip()

    st.markdown("## New application")
    st.caption(
        "Turn a complete job description into a channel-aware, evidence-grounded application pack."
    )

    current = application.normalize_initial_job_text(st.session_state.get("job_text"))
    if st.session_state.get("job_text") != current:
        st.session_state["job_text"] = current

    with st.container(border=True):
        st.markdown(
            '<div class="jc-step">Step 1 · Opportunity</div>',
            unsafe_allow_html=True,
        )
        job_text = st.text_area(
            "Job description",
            height=280,
            key="job_text",
            placeholder=application.JOB_PLACEHOLDER,
            label_visibility="collapsed",
        )
        st.caption(
            f"{len(job_text.strip()):,} characters · include application instructions when they are available"
        )
        analyze = st.button(
            "Analyze offer and build application pack",
            type="primary",
            use_container_width=True,
            disabled=len(job_text.strip()) < 40,
            key="hosted_analyze_offer",
        )

    if analyze:
        with st.status(
            "Understanding the offer and retrieving verified evidence…",
            expanded=True,
        ) as status:
            try:
                st.write("Extracting role and application instructions")
                results = application._run_pipeline(user_id, candidate_name, job_text)
                st.session_state["results"] = results
                st.write("Ranking verified profile evidence")
                st.write("Building the channel-aware application pack")
                status.update(
                    label="Application pack ready",
                    state="complete",
                    expanded=False,
                )
            except UsageQuotaExceeded as exc:
                status.update(label="Daily AI quota reached", state="error")
                st.warning(str(exc))
            except Exception as exc:
                status.update(
                    label="The analysis could not be completed",
                    state="error",
                )
                st.error(
                    f"JobCopilot could not complete this analysis ({type(exc).__name__}). "
                    "Check the offer and try again."
                )

    results = st.session_state.get("results")
    if not results:
        st.markdown(
            """
            <div class="jc-card" style="margin-top:1rem;text-align:center;padding:2rem">
              <div class="jc-card-title">Your application pack will appear here</div>
              <p class="jc-muted">JobCopilot will recommend a route, show CV priorities and prepare only the outputs that make sense for the offer.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    analysis = results["job_analysis"]
    match = results["match"]
    draft = results["email_draft"]
    pack = results["application_pack"]
    events = results.get("llm_telemetry", [])
    claims = draft.get("claim_evidence", [])
    memory_records = results.get("retrieved_memory_records", [])

    st.markdown(
        f"""
        <div class="jc-hero" style="margin-top:1.25rem">
          <div class="jc-eyebrow">Evidence-grounded application</div>
          <h1>{escape(str(analysis.get('role', 'Unknown role')))}</h1>
          <p>{escape(str(analysis.get('company', 'Unknown company')))} · {escape(str(analysis.get('location', 'Unknown location')))} · {escape(str(analysis.get('contract_type', 'Unknown contract')))}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    application._render_compact_ai_status(events, len(claims))

    overview_tab, match_tab, pack_tab, email_tab = st.tabs(
        [
            "Role & route",
            "Match & evidence",
            "Application pack",
            "Email & persistent save",
        ]
    )
    with overview_tab:
        application._render_role_overview(analysis)
    with match_tab:
        application._render_match_and_evidence(match, draft, memory_records)
    with pack_tab:
        render_application_pack(pack, memory_records)
    with email_tab:
        _render_hosted_email_actions(user_id, analysis, draft)

    application._render_technical_trace(events)


def render_agent_chat(user_id: str) -> None:
    """Render the agent with only non-Google hosted actions exposed."""
    st.markdown("## Agent Chat")
    st.caption(
        "A tenant-isolated copilot for role analysis, grounded application content and saved applications."
    )

    _, top_right = st.columns([4, 1])
    with top_right:
        if st.button("New chat", use_container_width=True, key="hosted-new-chat"):
            premium._reset_agent_chat(user_id)
            st.rerun()

    st.markdown("**Try a guided action**")
    s1, s2, s3 = st.columns(3)
    suggestions = [
        (s1, "Show my saved applications and identify missing follow-ups."),
        (s2, "Help me assess whether a new role matches my verified profile."),
        (s3, "Explain how JobCopilot prevents unsupported candidate claims."),
    ]
    for index, (column, prompt) in enumerate(suggestions):
        with column:
            if st.button(prompt, use_container_width=True, key=f"hosted-agent-suggestion-{index}"):
                premium._handle_agent_prompt(user_id, prompt)

    messages = st.session_state.get("agent_messages", [])
    if not messages:
        st.info(
            "This hosted demo exposes analysis, grounding and tracker tools. Gmail and Calendar actions are disabled by design."
        )
    for message in messages:
        if isinstance(message, HumanMessage):
            with st.chat_message("user"):
                st.markdown(premium._message_to_text(message.content))
        elif isinstance(message, AIMessage):
            text = premium._message_to_text(message.content).strip()
            if text:
                with st.chat_message("assistant"):
                    st.markdown(text)
        elif isinstance(message, ToolMessage):
            with st.expander("Verified agent action"):
                st.code(premium._message_to_text(message.content))

    premium._render_provider_trace(
        st.session_state.get("agent_telemetry", []),
        compact=True,
    )
    user_input = st.chat_input("Ask JobCopilot…")
    if user_input:
        premium._handle_agent_prompt(user_id, user_input)


def render_settings(user_id: str) -> None:
    """Render hosted-demo privacy controls without local OAuth configuration."""
    paths = get_user_paths(user_id)
    st.markdown("## Settings & privacy")

    c1, c2 = st.columns(2)
    with c1:
        with st.container(border=True):
            st.markdown("### Hosted demo boundary")
            st.write("Persistence: **Supabase**")
            st.write("Google actions: **Disabled**")
            st.write("Raw CV uploads: **Not persisted**")
            st.caption(
                "FAISS indexes and temporary runtime files may be rebuilt on the Streamlit instance. "
                "Verified profile facts, tracker state, beta account data and quotas are durable."
            )
    with c2:
        with st.container(border=True):
            st.markdown("### AI transparency")
            st.write(f"Primary provider: **{settings.llm_provider.title()}**")
            fallback = (
                settings.llm_fallback_provider.title()
                if settings.llm_fallback_provider
                else "Disabled"
            )
            st.write(f"Fallback: **{fallback}**")
            st.caption(
                "Telemetry stores provider, model, operation, status, latency and available token counts. "
                "It never stores prompts, generated content, API keys or raw provider errors."
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

    with st.expander("Danger zone"):
        st.warning(
            "Deleting application data removes the verified profile, tracker state and quota ledger. "
            "The private-beta login is preserved so the tester can start again."
        )
        confirmation = st.text_input(
            "Type DELETE to confirm",
            key="hosted_delete_confirmation",
        )
        if st.button(
            "Delete my application data",
            use_container_width=True,
            key="hosted-delete-data",
        ):
            if confirmation != "DELETE":
                st.warning("Type DELETE exactly before continuing.")
            else:
                delete_user_data(user_id)
                st.session_state.pop("results", None)
                premium._reset_agent_chat(user_id)
                st.success("Application data deleted. Your beta login remains active.")
                st.rerun()
