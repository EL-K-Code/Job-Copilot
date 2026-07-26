from __future__ import annotations

import json
import sys
from datetime import date, timedelta
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
)
from app.services.profile_store import (
    delete_user_data,
    export_user_data,
    save_user_profile_memories,
)
from app.tenancy import DEFAULT_LOCAL_USER_ID, ensure_user_directories, get_user_paths
from app.tools.calendar_tools import build_followup_event_payload, create_followup_event
from app.tools.gmail_tools import create_gmail_draft, get_google_credentials, google_token_exists


DEFAULT_JOB_TEXT = """Paste a complete job description here."""


def _logout() -> None:
    for key in list(st.session_state):
        del st.session_state[key]
    st.rerun()


def _authenticated_user() -> dict[str, str] | None:
    if not settings.beta_auth_enabled:
        return {
            "user_id": DEFAULT_LOCAL_USER_ID,
            "display_name": "Local demo",
        }

    current = st.session_state.get("authenticated_user")
    if current:
        return current

    st.title("JobCopilot Private Beta")
    st.caption("Sign in with the private beta account created for you.")
    with st.form("beta-login"):
        user_id = st.text_input("User ID")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in", use_container_width=True)

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


def _run_pipeline(user_id: str, job_text: str) -> dict:
    from app.graph import jobcopilot_graph

    result = jobcopilot_graph.invoke(
        {"user_id": user_id, "job_text": job_text},
        config={"configurable": {"thread_id": f"private-beta-{user_id}"}},
    )
    return {
        "job_analysis": result["job_analysis"],
        "retrieved_memories": result["retrieved_memories"],
        "match": result["match_insight"],
        "email_draft": result["email_draft"],
    }


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


def _initialize_agent_session(user_id: str) -> None:
    """Create a fresh, user-namespaced chat thread after login or account switch."""
    if st.session_state.get("agent_user_id") == user_id:
        return
    st.session_state["agent_user_id"] = user_id
    st.session_state["agent_thread_id"] = f"agent-{user_id}-{uuid4()}"
    st.session_state["agent_messages"] = []


def _run_agent_chat_turn(user_id: str, user_input: str) -> None:
    from app.agent_graph import get_jobcopilot_agent_graph

    graph = get_jobcopilot_agent_graph(user_id)
    result = graph.invoke(
        {"messages": [HumanMessage(content=user_input)]},
        config={
            "configurable": {
                "thread_id": st.session_state["agent_thread_id"],
            }
        },
    )
    st.session_state["agent_messages"] = result["messages"]


def _reset_agent_chat(user_id: str) -> None:
    st.session_state["agent_user_id"] = user_id
    st.session_state["agent_thread_id"] = f"agent-{user_id}-{uuid4()}"
    st.session_state["agent_messages"] = []
    st.success("Agent chat reset for your workspace.")


def _render_profile_onboarding(user_id: str) -> bool:
    paths = ensure_user_directories(user_id)
    if paths.profile_memories.exists():
        return True

    st.warning("Your private profile memory has not been configured yet.")
    st.write(
        "Upload a verified JSON list of atomic profile memories. Each item must contain "
        "`id`, `type` and `content`."
    )
    upload = st.file_uploader("Profile memories JSON", type=["json"])
    if upload is not None:
        try:
            payload = json.loads(upload.getvalue().decode("utf-8"))
            if not isinstance(payload, list):
                raise ValueError("The uploaded JSON must contain a list.")
            save_user_profile_memories(user_id, payload)
            st.success("Private profile saved. Reloading your workspace.")
            st.rerun()
        except Exception as exc:
            st.exception(exc)
    return False


def _render_analysis(user_id: str) -> None:
    st.subheader("New application")
    job_text = st.text_area(
        "Job offer",
        value=st.session_state.get("job_text", DEFAULT_JOB_TEXT),
        height=300,
        key="job_text",
    )

    if st.button("Analyze and draft", type="primary", use_container_width=True):
        if not job_text.strip() or job_text.strip() == DEFAULT_JOB_TEXT:
            st.warning("Paste a complete job offer first.")
        else:
            with st.spinner("Analyzing the offer against your private profile..."):
                try:
                    st.session_state["results"] = _run_pipeline(user_id, job_text)
                except Exception as exc:
                    st.exception(exc)

    results = st.session_state.get("results")
    if not results:
        return

    analysis = results["job_analysis"]
    draft = results["email_draft"]

    st.divider()
    st.write(f"**{analysis['company']} — {analysis['role']}**")
    st.caption(
        f"{analysis['location']} · {analysis['contract_type']} · {analysis['start_date']}"
    )

    with st.expander("Retrieved evidence"):
        for memory in results["retrieved_memories"]:
            st.write(f"- {memory}")

    subject = st.text_input(
        "Email subject",
        value=draft["subject"],
        key="beta_email_subject",
    )
    body = st.text_area(
        "Email body",
        value=draft["body"],
        height=360,
        key="beta_email_body",
    )
    recipient = st.text_input("Recipient email", key="beta_recipient")
    followup_date = st.date_input(
        "Follow-up date",
        value=date.today() + timedelta(days=5),
        min_value=date.today(),
        key="beta_followup_date",
    )

    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("Save application", use_container_width=True):
            existing = find_existing_application(
                analysis["company"],
                analysis["role"],
                user_id=user_id,
            )
            if existing:
                st.warning("This application already exists in your workspace.")
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
                st.success("Application saved in your private workspace.")

    with c2:
        if st.button("Create Gmail draft", use_container_width=True):
            try:
                result = create_gmail_draft(
                    to=recipient,
                    subject=subject,
                    body=body,
                    user_id=user_id,
                )
                st.success(f"Gmail draft created: {result.get('draft_id', '')}")
            except Exception as exc:
                st.exception(exc)

    with c3:
        if st.button("Create reminder", use_container_width=True):
            try:
                payload = build_followup_event_payload(
                    company=analysis["company"],
                    role=analysis["role"],
                    followup_date=str(followup_date),
                )
                result = create_followup_event(**payload, user_id=user_id)
                st.success(f"Calendar event created: {result.get('event_id', '')}")
            except Exception as exc:
                st.exception(exc)


def _render_agent_chat(user_id: str) -> None:
    st.subheader("Agent Chat")
    st.caption(
        "The agent can analyze offers, inspect your applications and prepare Gmail or "
        "Calendar actions. External actions still require explicit confirmation."
    )

    if st.button("Reset my agent chat", use_container_width=True):
        _reset_agent_chat(user_id)

    messages = st.session_state.get("agent_messages", [])
    if not messages:
        st.info(
            "Example: Paste a job offer and ask JobCopilot to analyze it and draft an email."
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
            with st.expander("Agent tool output"):
                st.code(_message_to_text(message.content))

    user_input = st.chat_input("Ask JobCopilot agent...")
    if user_input:
        with st.chat_message("user"):
            st.markdown(user_input)
        with st.spinner("Agent is working in your private workspace..."):
            try:
                _run_agent_chat_turn(user_id, user_input)
                st.rerun()
            except Exception as exc:
                st.exception(exc)


def _render_applications(user_id: str) -> None:
    st.subheader("My applications")
    records = load_application_records(user_id=user_id)
    if not records:
        st.info("No application saved in your workspace yet.")
        return
    st.metric("Saved applications", len(records))
    for record in reversed(records):
        with st.expander(f"{record.company} — {record.role} [{record.status}]"):
            st.write(f"**Created:** {record.created_at}")
            st.write(f"**Reminder:** {record.reminder_date or 'None'}")
            st.write(f"**Subject:** {record.email_subject or 'None'}")
            if record.notes:
                st.write(f"**Notes:** {record.notes}")


def _render_settings(user_id: str) -> None:
    st.subheader("Privacy and connections")
    paths = get_user_paths(user_id)
    st.write(f"Private workspace: `{paths.root}`")
    st.write(f"Google connected: **{'Yes' if google_token_exists(user_id) else 'No'}**")

    if st.button("Connect or refresh Google", use_container_width=True):
        try:
            get_google_credentials(interactive=True, user_id=user_id)
            st.success("Google account connected for this user only.")
        except Exception as exc:
            st.exception(exc)

    export_bytes = export_user_data(user_id)
    st.download_button(
        "Export my data",
        data=export_bytes,
        file_name=f"jobcopilot-{user_id}-export.zip",
        mime="application/zip",
        use_container_width=True,
    )

    st.divider()
    confirmation = st.text_input(
        "Type DELETE to remove your private workspace",
        key="delete_confirmation",
    )
    if st.button("Delete my data", type="secondary", use_container_width=True):
        if confirmation != "DELETE":
            st.warning("Type DELETE exactly before deleting your data.")
        else:
            delete_user_data(user_id)
            st.session_state.pop("results", None)
            _reset_agent_chat(user_id)
            st.success("Your private workspace was deleted.")
            st.rerun()


def main() -> None:
    st.set_page_config(
        page_title="JobCopilot Private Beta",
        page_icon="📨",
        layout="wide",
    )

    user = _authenticated_user()
    if user is None:
        st.stop()

    user_id = user["user_id"]
    ensure_user_directories(user_id)
    _initialize_agent_session(user_id)

    with st.sidebar:
        st.title("JobCopilot")
        st.write(f"Signed in as **{user['display_name']}**")
        st.caption(f"User ID: `{user_id}`")
        if settings.beta_auth_enabled and st.button("Sign out", use_container_width=True):
            _logout()

    st.title("📨 JobCopilot Private Beta")
    st.caption(
        "Every profile, application record, FAISS index, Google token and agent "
        "conversation is scoped to the authenticated user."
    )

    if not _render_profile_onboarding(user_id):
        st.stop()

    tab1, tab2, tab3, tab4 = st.tabs(
        ["New application", "Agent Chat", "My applications", "Settings & privacy"]
    )
    with tab1:
        _render_analysis(user_id)
    with tab2:
        _render_agent_chat(user_id)
    with tab3:
        _render_applications(user_id)
    with tab4:
        _render_settings(user_id)


if __name__ == "__main__":
    main()
