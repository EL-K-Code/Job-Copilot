from __future__ import annotations

import json
import sys
from datetime import date, datetime, timedelta
from html import escape
from pathlib import Path
from uuid import uuid4

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.auth import authenticate_beta_user
from app.config import settings
from app.services.applications_store import (
    add_application_record,
    create_application_record,
    find_existing_application,
    load_application_records,
    update_application_record,
)
from app.services.llm_telemetry import (
    capture_llm_telemetry,
    serialize_llm_events,
    summarize_llm_events,
)
from app.services.profile_store import (
    delete_user_data,
    export_user_data,
    save_user_profile_memories,
)
from app.tenancy import DEFAULT_LOCAL_USER_ID, ensure_user_directories, get_user_paths
from app.tools.calendar_tools import build_followup_event_payload, create_followup_event
from app.tools.gmail_tools import create_gmail_draft, get_google_credentials, google_token_exists


DEFAULT_JOB_TEXT = "Paste the complete job description here."
NAV_ITEMS = ["Overview", "New application", "Agent Chat", "Applications", "Settings"]
STATUS_LABELS = {
    "drafted": "Draft",
    "applied": "Applied",
    "interview": "Interview",
    "follow_up": "Follow-up",
    "closed": "Closed",
}
STATUS_ICONS = {
    "drafted": "◌",
    "applied": "✓",
    "interview": "◆",
    "follow_up": "↗",
    "closed": "—",
}


PREMIUM_CSS = """
<style>
:root {
  --jc-navy: #0b1633;
  --jc-blue: #315efb;
  --jc-cyan: #5dd6ff;
  --jc-bg: #f4f7fb;
  --jc-card: #ffffff;
  --jc-muted: #667085;
  --jc-border: #e4e9f2;
}
.stApp { background: var(--jc-bg); }
[data-testid="stHeader"] { background: rgba(244,247,251,.88); backdrop-filter: blur(12px); }
[data-testid="stSidebar"] { background: var(--jc-navy); }
[data-testid="stSidebar"] * { color: #eef3ff; }
[data-testid="stSidebar"] [data-testid="stRadio"] label {
  border-radius: 10px; padding: .55rem .7rem; margin: .1rem 0;
}
[data-testid="stSidebar"] [data-testid="stRadio"] label:hover { background: rgba(255,255,255,.08); }
.block-container { max-width: 1320px; padding-top: 2rem; padding-bottom: 4rem; }
h1, h2, h3 { color: var(--jc-navy); letter-spacing: -.02em; }
.jc-brand { font-weight: 800; font-size: 1.35rem; letter-spacing: -.03em; }
.jc-brand-dot { color: var(--jc-cyan); }
.jc-hero {
  border-radius: 22px; padding: 2rem 2.2rem; color: white;
  background: radial-gradient(circle at 85% 20%, rgba(93,214,255,.32), transparent 28%),
              linear-gradient(135deg, #0b1633 0%, #173a8f 62%, #315efb 100%);
  box-shadow: 0 18px 45px rgba(11,22,51,.18); margin-bottom: 1.2rem;
}
.jc-hero h1 { color: white; margin: 0 0 .4rem; font-size: 2.15rem; }
.jc-hero p { color: #dfe8ff; margin: 0; max-width: 760px; }
.jc-eyebrow { text-transform: uppercase; letter-spacing: .13em; font-size: .72rem; font-weight: 700; opacity: .78; }
.jc-card {
  background: var(--jc-card); border: 1px solid var(--jc-border); border-radius: 16px;
  padding: 1.15rem 1.25rem; box-shadow: 0 7px 22px rgba(20,38,80,.055); height: 100%;
}
.jc-card-title { font-weight: 700; color: var(--jc-navy); margin-bottom: .25rem; }
.jc-muted { color: var(--jc-muted); font-size: .9rem; }
.jc-kpi { font-size: 1.85rem; font-weight: 800; color: var(--jc-navy); line-height: 1.1; }
.jc-pill {
  display: inline-block; border-radius: 999px; padding: .28rem .62rem; margin: .12rem .15rem .12rem 0;
  background: #edf2ff; color: #2448c8; font-size: .78rem; font-weight: 650;
}
.jc-pill-success { background: #eaf9f1; color: #147a4d; }
.jc-provider {
  border: 1px solid #dce5ff; background: #f7f9ff; border-radius: 12px;
  padding: .72rem .9rem; margin: .55rem 0;
}
.jc-provider strong { color: var(--jc-navy); }
.jc-step { color: var(--jc-blue); font-weight: 800; font-size: .78rem; letter-spacing: .08em; text-transform: uppercase; }
div[data-testid="stMetric"] {
  background: white; border: 1px solid var(--jc-border); border-radius: 15px;
  padding: .9rem 1rem; box-shadow: 0 6px 18px rgba(20,38,80,.045);
}
.stButton > button, .stDownloadButton > button, [data-testid="stFormSubmitButton"] > button {
  border-radius: 10px; min-height: 2.65rem; font-weight: 700;
}
.stButton > button[kind="primary"], [data-testid="stFormSubmitButton"] > button[kind="primary"] {
  background: linear-gradient(135deg, #315efb, #2447d9); border: 0;
  box-shadow: 0 8px 18px rgba(49,94,251,.22);
}
[data-testid="stTextInput"] input, [data-testid="stTextArea"] textarea, [data-testid="stSelectbox"] > div > div {
  border-radius: 10px;
}
[data-testid="stChatMessage"] { border-radius: 14px; border: 1px solid var(--jc-border); background: white; }
hr { border-color: var(--jc-border); }
</style>
"""


def _inject_theme() -> None:
    st.markdown(PREMIUM_CSS, unsafe_allow_html=True)


def _request_navigation(page: str) -> None:
    st.session_state["pending_nav_page"] = page
    st.rerun()


def _logout() -> None:
    for key in list(st.session_state):
        del st.session_state[key]
    st.rerun()


def _authenticated_user() -> dict[str, str] | None:
    if not settings.beta_auth_enabled:
        return {"user_id": DEFAULT_LOCAL_USER_ID, "display_name": "Local demo"}

    current = st.session_state.get("authenticated_user")
    if current:
        return current

    _, center, _ = st.columns([1, 1.15, 1])
    with center:
        st.markdown(
            """
            <div class="jc-hero" style="margin-top:4rem;text-align:center">
              <div class="jc-eyebrow">Private beta</div>
              <h1>JobCopilot</h1>
              <p>Your evidence-grounded workspace for stronger, faster job applications.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        with st.form("beta-login"):
            st.markdown("### Welcome back")
            user_id = st.text_input("User ID", placeholder="alex")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button(
                "Sign in securely",
                type="primary",
                use_container_width=True,
            )
        st.caption(
            "Your profile, applications, Google token and agent conversations are isolated from every other tester."
        )

    if submitted:
        try:
            user = authenticate_beta_user(user_id, password)
        except Exception as exc:
            st.error(str(exc))
            return None
        if user is None:
            st.error("Invalid or disabled private beta account.")
            return None
        st.session_state["authenticated_user"] = user
        st.rerun()
    return None


def _initialize_agent_session(user_id: str) -> None:
    if st.session_state.get("agent_user_id") == user_id:
        return
    st.session_state["agent_user_id"] = user_id
    st.session_state["agent_thread_id"] = f"agent-{user_id}-{uuid4()}"
    st.session_state["agent_messages"] = []
    st.session_state["agent_telemetry"] = []


def _reset_agent_chat(user_id: str) -> None:
    st.session_state["agent_user_id"] = user_id
    st.session_state["agent_thread_id"] = f"agent-{user_id}-{uuid4()}"
    st.session_state["agent_messages"] = []
    st.session_state["agent_telemetry"] = []


def _message_to_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(str(item.get("text", item)))
            else:
                parts.append(str(item))
        return "\n".join(part for part in parts if part)
    return str(content)


def _run_pipeline(user_id: str, job_text: str) -> dict:
    from app.graph import jobcopilot_graph

    with capture_llm_telemetry() as events:
        result = jobcopilot_graph.invoke(
            {"user_id": user_id, "job_text": job_text},
            config={
                "configurable": {
                    "thread_id": f"private-beta-{user_id}-{uuid4()}"
                }
            },
        )
    serialized = serialize_llm_events(events)
    return {
        "job_analysis": result["job_analysis"],
        "retrieved_memories": result["retrieved_memories"],
        "retrieved_memory_records": result.get("retrieved_memory_records", []),
        "match": result["match_insight"],
        "email_draft": result["email_draft"],
        "llm_telemetry": serialized,
        "llm_telemetry_summary": summarize_llm_events(serialized),
    }


def _run_agent_chat_turn(user_id: str, user_input: str) -> None:
    from app.agent_graph import get_jobcopilot_agent_graph

    graph = get_jobcopilot_agent_graph(user_id)
    with capture_llm_telemetry() as events:
        result = graph.invoke(
            {"messages": [HumanMessage(content=user_input)]},
            config={
                "configurable": {
                    "thread_id": st.session_state["agent_thread_id"]
                }
            },
        )
    st.session_state["agent_messages"] = result["messages"]
    st.session_state["agent_telemetry"] = serialize_llm_events(events)


def _render_provider_trace(events: list[dict], *, compact: bool = False) -> None:
    if not events:
        st.caption("Provider telemetry will appear after the next AI operation.")
        return

    summary = summarize_llm_events(events)
    provider = str(summary.get("final_provider") or "unknown").title()
    model = str(summary.get("final_model") or "unknown")
    fallback = " · fallback used" if summary.get("fallback_used") else ""
    duration = float(summary.get("total_duration_ms", 0) or 0) / 1000
    successful = int(summary.get("successful_calls", 0) or 0)
    failed = int(summary.get("failed_attempts", 0) or 0)
    trace_html = (
        '<div class="jc-provider">'
        f'<strong>AI trace:</strong> {escape(provider)} · {escape(model)} · {duration:.2f}s{fallback}<br>'
        f'<span class="jc-muted">{successful} successful call(s), {failed} failed attempt(s). '
        'No prompts, outputs or API keys recorded.</span>'
        '</div>'
    )
    st.markdown(trace_html, unsafe_allow_html=True)
    if not compact:
        with st.expander("Technical provider trace"):
            st.dataframe(events, use_container_width=True, hide_index=True)


def _render_profile_onboarding(user_id: str) -> bool:
    paths = ensure_user_directories(user_id)
    if paths.profile_memories.exists():
        return True

    st.markdown(
        """
        <div class="jc-hero">
          <div class="jc-eyebrow">Profile setup · 1 minute</div>
          <h1>Build your private evidence profile</h1>
          <p>Upload the verified profile file prepared for your beta account. JobCopilot will only use facts contained in this file.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    left, right = st.columns([1.35, 1])
    with left:
        upload = st.file_uploader(
            "Import my JobCopilot profile",
            type=["json"],
            help="The JSON remains in your private workspace.",
        )
        if upload is not None:
            try:
                payload = json.loads(upload.getvalue().decode("utf-8"))
                if not isinstance(payload, list):
                    raise ValueError(
                        "The profile file must contain a list of verified facts."
                    )
                required = {"id", "type", "content"}
                for item in payload:
                    if not isinstance(item, dict) or not required.issubset(item):
                        raise ValueError(
                            "Every profile fact must include id, type and content."
                        )
                st.session_state["pending_profile_payload"] = payload
            except Exception as exc:
                st.error(str(exc))

        payload = st.session_state.get("pending_profile_payload")
        if payload:
            counts: dict[str, int] = {}
            for item in payload:
                item_type = str(item.get("type", "other"))
                counts[item_type] = counts.get(item_type, 0) + 1
            c1, c2, c3 = st.columns(3)
            c1.metric("Verified facts", len(payload))
            c2.metric("Categories", len(counts))
            c3.metric("Storage", "Private")
            with st.expander("Preview imported facts"):
                for item in payload[:8]:
                    st.write(
                        f"**{item.get('type', 'Fact').title()}** — {item.get('content', '')}"
                    )
                if len(payload) > 8:
                    st.caption(f"+ {len(payload) - 8} additional facts")
            if st.button(
                "Activate my profile",
                type="primary",
                use_container_width=True,
            ):
                save_user_profile_memories(user_id, payload)
                st.session_state.pop("pending_profile_payload", None)
                st.success("Your private profile is active.")
                st.rerun()
    with right:
        st.markdown(
            """
            <div class="jc-card">
              <div class="jc-card-title">Why this matters</div>
              <p class="jc-muted">Every factual statement in an application email is linked to a verified profile fact. JobCopilot prefers a shorter honest email over unsupported claims.</p>
              <span class="jc-pill jc-pill-success">Evidence grounded</span>
              <span class="jc-pill">User isolated</span>
              <span class="jc-pill">Exportable</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    return False


def _parse_date(value: str) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _render_overview(user: dict[str, str]) -> None:
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
          <div class="jc-eyebrow">Your private application workspace</div>
          <h1>Welcome back, {escape(user['display_name'])}</h1>
          <p>Turn job descriptions into evidence-grounded applications, then track every next step from one place.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Applications", len(records))
    c2.metric("Active", len(active))
    c3.metric("Interviews", len(interviews))
    c4.metric("Due this week", len(upcoming))

    st.markdown("### Quick actions")
    q1, q2, q3 = st.columns(3)
    with q1:
        st.markdown(
            '<div class="jc-card"><div class="jc-card-title">Analyze a new opportunity</div><p class="jc-muted">Paste an offer and receive a grounded email draft.</p></div>',
            unsafe_allow_html=True,
        )
        if st.button(
            "Start an application",
            type="primary",
            use_container_width=True,
        ):
            _request_navigation("New application")
    with q2:
        st.markdown(
            '<div class="jc-card"><div class="jc-card-title">Work with Agent Chat</div><p class="jc-muted">Ask about offers, saved applications or follow-ups.</p></div>',
            unsafe_allow_html=True,
        )
        if st.button("Open Agent Chat", use_container_width=True):
            _request_navigation("Agent Chat")
    with q3:
        connected = google_token_exists(user_id)
        status = "Connected" if connected else "Not connected"
        st.markdown(
            f'<div class="jc-card"><div class="jc-card-title">Google connection</div><p class="jc-muted">Status: <strong>{status}</strong></p></div>',
            unsafe_allow_html=True,
        )
        if st.button("Manage connections", use_container_width=True):
            _request_navigation("Settings")

    left, right = st.columns([1.7, 1])
    with left:
        st.markdown("### Recent applications")
        if not records:
            st.info("Your application tracker is empty. Start with one opportunity.")
        else:
            rows = [
                {
                    "Company": record.company,
                    "Role": record.role,
                    "Status": STATUS_LABELS[record.status],
                    "Reminder": record.reminder_date or "—",
                }
                for record in reversed(records[-6:])
            ]
            st.dataframe(rows, use_container_width=True, hide_index=True)
    with right:
        st.markdown("### AI transparency")
        model = (
            settings.openai_model
            if settings.llm_provider == "openai"
            else settings.anthropic_model
        )
        st.markdown(
            f"""
            <div class="jc-card">
              <div class="jc-card-title">Configured provider</div>
              <div class="jc-kpi" style="font-size:1.25rem">{escape(settings.llm_provider.title())}</div>
              <p class="jc-muted">Model: {escape(model)}</p>
              <p class="jc-muted">Every new run displays the provider that actually completed each call.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _render_analysis(user_id: str) -> None:
    st.markdown("## New application")
    st.caption("A guided workspace from raw offer to reviewed email draft.")

    with st.container(border=True):
        st.markdown(
            '<div class="jc-step">Step 1 · Opportunity</div>',
            unsafe_allow_html=True,
        )
        job_text = st.text_area(
            "Job description",
            value=st.session_state.get("job_text", DEFAULT_JOB_TEXT),
            height=280,
            key="job_text",
            label_visibility="collapsed",
        )
        analyze = st.button(
            "Analyze offer and prepare draft",
            type="primary",
            use_container_width=True,
        )

    if analyze:
        if not job_text.strip() or job_text.strip() == DEFAULT_JOB_TEXT:
            st.warning("Paste a complete job description first.")
        else:
            with st.status(
                "Understanding the offer and retrieving verified evidence…",
                expanded=True,
            ) as status:
                try:
                    st.write("Extracting role requirements")
                    st.session_state["results"] = _run_pipeline(user_id, job_text)
                    st.write("Ranking profile evidence")
                    st.write("Composing the grounded email")
                    status.update(
                        label="Application workspace ready",
                        state="complete",
                        expanded=False,
                    )
                except Exception as exc:
                    status.update(
                        label="The analysis could not be completed",
                        state="error",
                    )
                    st.exception(exc)

    results = st.session_state.get("results")
    if not results:
        st.markdown(
            """
            <div class="jc-card" style="margin-top:1rem;text-align:center;padding:2rem">
              <div class="jc-card-title">Your result will appear here</div>
              <p class="jc-muted">Job summary, match evidence, editable email and next actions will be organized into clear sections.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    analysis = results["job_analysis"]
    match = results["match"]
    draft = results["email_draft"]
    st.markdown(
        f"""
        <div class="jc-hero" style="margin-top:1.25rem">
          <div class="jc-eyebrow">Application workspace</div>
          <h1>{escape(analysis['role'])}</h1>
          <p>{escape(analysis['company'])} · {escape(analysis['location'])} · {escape(analysis['contract_type'])}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    _render_provider_trace(results.get("llm_telemetry", []))

    overview_tab, match_tab, email_tab = st.tabs(
        ["Role overview", "Match & evidence", "Email & actions"]
    )
    with overview_tab:
        a, b = st.columns(2)
        with a:
            st.markdown("#### Main responsibilities")
            for item in analysis.get("missions_summary", []):
                st.write(f"• {item}")
            st.markdown("#### Required skills")
            pills = " ".join(
                f'<span class="jc-pill">{escape(item)}</span>'
                for item in analysis.get("required_skills", [])
            )
            st.markdown(pills or "—", unsafe_allow_html=True)
        with b:
            st.markdown("#### Tools and stack")
            pills = " ".join(
                f'<span class="jc-pill">{escape(item)}</span>'
                for item in analysis.get("tools_and_stack", [])
            )
            st.markdown(pills or "—", unsafe_allow_html=True)
            st.markdown("#### Domain focus")
            pills = " ".join(
                f'<span class="jc-pill">{escape(item)}</span>'
                for item in analysis.get("domain_focus", [])
            )
            st.markdown(pills or "—", unsafe_allow_html=True)
    with match_tab:
        m1, m2 = st.columns(2)
        with m1:
            st.markdown("#### Strong alignment")
            for item in match.get("strengths", []):
                st.success(item)
        with m2:
            st.markdown("#### Points to handle honestly")
            for item in match.get("gaps", []):
                st.warning(item)
        st.markdown("#### Evidence ledger")
        claims = draft.get("claim_evidence", [])
        if not claims:
            st.info("No factual claim ledger was returned.")
        for claim in claims:
            with st.container(border=True):
                st.write(f"**{claim.get('claim', '')}**")
                terms = claim.get("aligned_job_terms", [])
                st.caption(
                    f"Evidence: {', '.join(claim.get('supporting_memory_ids', []))} · "
                    f"Relevance: {claim.get('relevance_score', 0):.2f} · "
                    f"Aligned terms: {', '.join(terms) or 'none'}"
                )
    with email_tab:
        st.markdown(
            '<div class="jc-step">Step 2 · Review the message</div>',
            unsafe_allow_html=True,
        )
        subject = st.text_input(
            "Subject",
            value=draft["subject"],
            key="beta_email_subject",
        )
        body = st.text_area(
            "Email body",
            value=draft["body"],
            height=360,
            key="beta_email_body",
        )
        st.markdown(
            '<div class="jc-step">Step 3 · Choose the next action</div>',
            unsafe_allow_html=True,
        )
        recipient = st.text_input(
            "Recruiter email",
            key="beta_recipient",
            placeholder="recruiter@company.com",
        )
        followup_date = st.date_input(
            "Follow-up date",
            value=date.today() + timedelta(days=5),
            min_value=date.today(),
            key="beta_followup_date",
        )
        reviewed = st.checkbox(
            "I reviewed the recipient, subject and email body."
        )
        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("Save to tracker", use_container_width=True):
                existing = find_existing_application(
                    analysis["company"],
                    analysis["role"],
                    user_id=user_id,
                )
                if existing:
                    st.warning("This application already exists in your tracker.")
                else:
                    record = create_application_record(
                        company=analysis["company"],
                        role=analysis["role"],
                        email_subject=subject,
                        email_body=body,
                        source="private-beta",
                        reminder_date=str(followup_date),
                    )
                    add_application_record(record, user_id=user_id)
                    st.success("Saved to your private tracker.")
        with c2:
            if st.button(
                "Create Gmail draft",
                type="primary",
                use_container_width=True,
            ):
                if not reviewed or not recipient.strip():
                    st.warning(
                        "Review the message and enter the recruiter email first."
                    )
                else:
                    try:
                        result = create_gmail_draft(
                            to=recipient,
                            subject=subject,
                            body=body,
                            user_id=user_id,
                        )
                        st.success(
                            f"Gmail draft created: {result.get('draft_id', '')}"
                        )
                    except Exception as exc:
                        st.exception(exc)
        with c3:
            if st.button("Add follow-up", use_container_width=True):
                try:
                    payload = build_followup_event_payload(
                        company=analysis["company"],
                        role=analysis["role"],
                        followup_date=str(followup_date),
                    )
                    result = create_followup_event(**payload, user_id=user_id)
                    st.success(
                        f"Calendar event created: {result.get('event_id', '')}"
                    )
                except Exception as exc:
                    st.exception(exc)


def _handle_agent_prompt(user_id: str, prompt: str) -> None:
    with st.spinner("JobCopilot is working inside your private workspace…"):
        try:
            _run_agent_chat_turn(user_id, prompt)
            st.rerun()
        except Exception as exc:
            st.exception(exc)


def _render_agent_chat(user_id: str) -> None:
    st.markdown("## Agent Chat")
    st.caption(
        "A tenant-isolated copilot for applications, drafts and follow-ups."
    )

    _, top_right = st.columns([4, 1])
    with top_right:
        if st.button("New chat", use_container_width=True):
            _reset_agent_chat(user_id)
            st.rerun()

    st.markdown("**Try a guided action**")
    s1, s2, s3 = st.columns(3)
    suggestions = [
        (s1, "Show my saved applications and identify missing follow-ups."),
        (s2, "Help me assess whether a new role matches my verified profile."),
        (s3, "Explain how JobCopilot keeps my application claims grounded."),
    ]
    for column, prompt in suggestions:
        with column:
            if st.button(prompt, use_container_width=True):
                _handle_agent_prompt(user_id, prompt)

    messages = st.session_state.get("agent_messages", [])
    if not messages:
        st.info(
            "Paste a job offer or ask about your saved applications. External Gmail and Calendar actions still require explicit confirmation."
        )
    for message in messages:
        if isinstance(message, HumanMessage):
            with st.chat_message("user"):
                st.markdown(_message_to_text(message.content))
        elif isinstance(message, AIMessage):
            text = _message_to_text(message.content).strip()
            if text:
                with st.chat_message("assistant"):
                    st.markdown(text)
        elif isinstance(message, ToolMessage):
            with st.expander("Verified agent action"):
                st.code(_message_to_text(message.content))

    _render_provider_trace(
        st.session_state.get("agent_telemetry", []),
        compact=True,
    )
    user_input = st.chat_input("Ask JobCopilot…")
    if user_input:
        _handle_agent_prompt(user_id, user_input)


def _render_applications(user_id: str) -> None:
    st.markdown("## Application tracker")
    records = load_application_records(user_id=user_id)
    if not records:
        st.info("No application saved yet.")
        if st.button("Create my first application", type="primary"):
            _request_navigation("New application")
        return

    filter_col, search_col = st.columns([1, 2])
    with filter_col:
        status_filter = st.selectbox(
            "Status",
            ["All", *STATUS_LABELS.values()],
        )
    with search_col:
        query = st.text_input("Search", placeholder="Company or role")

    filtered = []
    for record in records:
        if (
            status_filter != "All"
            and STATUS_LABELS[record.status] != status_filter
        ):
            continue
        if (
            query.strip()
            and query.lower() not in f"{record.company} {record.role}".lower()
        ):
            continue
        filtered.append(record)

    st.caption(f"{len(filtered)} of {len(records)} applications")
    rows = [
        {
            "Company": record.company,
            "Role": record.role,
            "Status": f"{STATUS_ICONS[record.status]} {STATUS_LABELS[record.status]}",
            "Reminder": record.reminder_date or "—",
            "Created": record.created_at[:10] if record.created_at else "—",
        }
        for record in reversed(filtered)
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)

    st.markdown("### Manage applications")
    for index, record in enumerate(reversed(filtered)):
        with st.expander(
            f"{record.company} — {record.role} · {STATUS_LABELS[record.status]}"
        ):
            c1, c2 = st.columns(2)
            with c1:
                statuses = list(STATUS_LABELS)
                new_status = st.selectbox(
                    "Status",
                    statuses,
                    index=statuses.index(record.status),
                    format_func=lambda value: STATUS_LABELS[value],
                    key=f"status-{index}-{record.company}-{record.role}",
                )
            with c2:
                current_reminder = (
                    _parse_date(record.reminder_date) or date.today()
                )
                new_reminder = st.date_input(
                    "Reminder",
                    value=current_reminder,
                    key=f"reminder-{index}-{record.company}-{record.role}",
                )
            notes = st.text_area(
                "Notes",
                value=record.notes,
                key=f"notes-{index}-{record.company}-{record.role}",
            )
            if st.button(
                "Update application",
                key=f"update-{index}-{record.company}-{record.role}",
            ):
                updated = update_application_record(
                    record.company,
                    record.role,
                    user_id=user_id,
                    status=new_status,
                    reminder_date=str(new_reminder),
                    notes=notes,
                )
                if updated:
                    st.success("Application updated.")
                    st.rerun()


def _render_settings(user_id: str) -> None:
    st.markdown("## Settings & privacy")
    paths = get_user_paths(user_id)
    connected = google_token_exists(user_id)

    c1, c2 = st.columns(2)
    with c1:
        with st.container(border=True):
            st.markdown("### Google workspace")
            st.write(
                f"Connection status: **{'Connected' if connected else 'Not connected'}**"
            )
            st.caption(
                "Each tester receives a separate OAuth token. No other account can use it."
            )
            if st.button(
                "Connect or refresh Google",
                type="primary",
                use_container_width=True,
            ):
                try:
                    get_google_credentials(interactive=True, user_id=user_id)
                    st.success("Google connected for this account only.")
                except Exception as exc:
                    st.exception(exc)
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
                "Telemetry stores provider, model, operation, status, latency and available token counts. It never stores prompts, generated content, API keys or raw provider errors."
            )

    with st.container(border=True):
        st.markdown("### Your data")
        st.caption(f"Private workspace: {paths.root}")
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
            "Deleting your workspace removes profile memories, applications, FAISS index and Google token."
        )
        confirmation = st.text_input(
            "Type DELETE to confirm",
            key="delete_confirmation",
        )
        if st.button(
            "Delete my private workspace",
            use_container_width=True,
        ):
            if confirmation != "DELETE":
                st.warning("Type DELETE exactly before continuing.")
            else:
                delete_user_data(user_id)
                st.session_state.pop("results", None)
                _reset_agent_chat(user_id)
                st.success("Your private workspace was deleted.")
                st.rerun()


def _render_sidebar(user: dict[str, str]) -> str:
    pending = st.session_state.pop("pending_nav_page", None)
    if pending in NAV_ITEMS:
        st.session_state["nav_radio"] = pending

    with st.sidebar:
        st.markdown(
            '<div class="jc-brand">JobCopilot<span class="jc-brand-dot">.</span></div>',
            unsafe_allow_html=True,
        )
        st.caption("Private beta workspace")
        st.divider()
        page = st.radio(
            "Navigation",
            NAV_ITEMS,
            key="nav_radio",
            label_visibility="collapsed",
        )
        st.divider()
        st.write(f"**{user['display_name']}**")
        st.caption(f"Workspace: {user['user_id']}")
        if google_token_exists(user["user_id"]):
            st.success("Google connected")
        else:
            st.info("Google not connected")
        if settings.beta_auth_enabled and st.button(
            "Sign out",
            use_container_width=True,
        ):
            _logout()
    return page


def main() -> None:
    st.set_page_config(
        page_title="JobCopilot Private Beta",
        page_icon="✦",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    _inject_theme()

    user = _authenticated_user()
    if user is None:
        st.stop()

    user_id = user["user_id"]
    ensure_user_directories(user_id)
    _initialize_agent_session(user_id)

    if not _render_profile_onboarding(user_id):
        st.stop()

    page = _render_sidebar(user)
    if page == "Overview":
        _render_overview(user)
    elif page == "New application":
        _render_analysis(user_id)
    elif page == "Agent Chat":
        _render_agent_chat(user_id)
    elif page == "Applications":
        _render_applications(user_id)
    else:
        _render_settings(user_id)
