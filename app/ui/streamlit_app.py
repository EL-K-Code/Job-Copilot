from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.services.applications_store import (
    add_application_record,
    create_application_record,
    find_existing_application,
    has_existing_reminder,
    load_application_records,
)
from app.tools.calendar_tools import (
    build_followup_event_payload,
    create_followup_event,
)
from app.tools.gmail_tools import create_gmail_draft


DEFAULT_JOB_TEXT = """Andra Learning is hiring a Stage / Alternance — IA Agentic & Automatisation in Paris.

You will work directly with the CTO and AI Lead to build AI agents that automate and enrich
the learning experience of B2B sales teams.

Responsibilities:
- Design and implement agentic workflows
- Integrate LLMs such as Claude and GPT via APIs
- Build RAG pipelines
- Develop bots and connectors for Microsoft Teams, CRM, calendars, and search tools
- Set up monitoring and evaluation for AI outputs

Profile:
- Strong interest in generative AI and agentic systems
- Python and/or TypeScript
- Experience with LLM APIs
- Bonus: RAG, prompt engineering, agent frameworks, open source
"""


def _normalize_text(value: str) -> str:
    return " ".join(value.strip().lower().split())


def _message_to_text(content) -> str:
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                if item.get("type") == "text":
                    parts.append(item.get("text", ""))
                elif "text" in item:
                    parts.append(str(item["text"]))
                else:
                    parts.append(str(item))
            else:
                parts.append(str(item))
        return "\n".join(part for part in parts if part)

    return str(content)


def run_pipeline(job_text: str) -> dict:
    from app.graph import jobcopilot_graph

    result = jobcopilot_graph.invoke(
        {"job_text": job_text},
        config={"configurable": {"thread_id": "streamlit-jobcopilot"}},
    )

    return {
        "job_analysis": result["job_analysis"],
        "retrieved_memories": result["retrieved_memories"],
        "match": result["match_insight"],
        "email_draft": result["email_draft"],
    }


def initialize_session_state() -> None:
    defaults = {
        "results": None,
        "recipient_email": "",
        "editable_email_subject": "",
        "editable_email_body": "",
        "followup_date": date.today() + timedelta(days=5),
        "last_gmail_draft_signature": "",
        "last_calendar_signature": "",
        "agent_messages": [],
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    if "agent_thread_id" not in st.session_state:
        st.session_state["agent_thread_id"] = f"agent-chat-{uuid4()}"


def sync_editable_email_fields() -> None:
    results = st.session_state.get("results")
    if not results:
        return

    email_draft = results["email_draft"]
    st.session_state["editable_email_subject"] = email_draft["subject"]
    st.session_state["editable_email_body"] = email_draft["body"]


def _current_application_signature() -> str:
    results = st.session_state.get("results")
    if not results:
        return ""

    job_analysis = results["job_analysis"]
    return (
        f"{_normalize_text(job_analysis['company'])}|"
        f"{_normalize_text(job_analysis['role'])}"
    )


def save_current_application() -> None:
    results = st.session_state.get("results")
    if not results:
        st.warning("No analyzed application to save yet.")
        return

    job_analysis = results["job_analysis"]

    existing = find_existing_application(
        company=job_analysis["company"],
        role=job_analysis["role"],
    )

    if existing:
        st.warning(
            f"An application for '{existing.company} — {existing.role}' already exists "
            f"(created at {existing.created_at})."
        )
        return

    record = create_application_record(
        company=job_analysis["company"],
        role=job_analysis["role"],
        email_subject=st.session_state.get("editable_email_subject", "").strip(),
        email_body=st.session_state.get("editable_email_body", "").strip(),
        status="drafted",
        source="streamlit",
        notes="Saved from Streamlit UI.",
        reminder_date=str(st.session_state.get("followup_date", "")),
    )

    saved = add_application_record(record)

    if saved:
        st.success("Application record saved.")
    else:
        st.warning("This application already exists and was not saved again.")


def create_current_gmail_draft() -> None:
    results = st.session_state.get("results")
    recipient_email = st.session_state.get("recipient_email", "").strip()
    subject = st.session_state.get("editable_email_subject", "").strip()
    body = st.session_state.get("editable_email_body", "").strip()

    if not results:
        st.warning("No analyzed application available yet.")
        return

    if not recipient_email:
        st.warning("Please enter a recipient email first.")
        return

    if not subject:
        st.warning("Email subject is empty.")
        return

    if not body:
        st.warning("Email body is empty.")
        return

    draft_signature = (
        f"{_current_application_signature()}|"
        f"{_normalize_text(recipient_email)}|"
        f"{_normalize_text(subject)}|"
        f"{_normalize_text(body)}"
    )

    if st.session_state.get("last_gmail_draft_signature") == draft_signature:
        st.warning("This Gmail draft was already created in the current session.")
        return

    draft_result = create_gmail_draft(
        to=recipient_email,
        subject=subject,
        body=body,
    )

    st.session_state["last_gmail_draft_signature"] = draft_signature
    st.success("Gmail draft created successfully.")
    st.json(draft_result)


def create_current_followup_reminder() -> None:
    results = st.session_state.get("results")
    if not results:
        st.warning("No analyzed application available yet.")
        return

    job_analysis = results["job_analysis"]
    followup_date = str(st.session_state.get("followup_date"))

    calendar_signature = f"{_current_application_signature()}|{followup_date}"

    if st.session_state.get("last_calendar_signature") == calendar_signature:
        st.warning("This follow-up reminder was already created in the current session.")
        return

    if has_existing_reminder(
        company=job_analysis["company"],
        role=job_analysis["role"],
        reminder_date=followup_date,
    ):
        st.warning("A saved application already has this same reminder date.")
        return

    payload = build_followup_event_payload(
        company=job_analysis["company"],
        role=job_analysis["role"],
        followup_date=followup_date,
    )

    event_result = create_followup_event(**payload)

    st.session_state["last_calendar_signature"] = calendar_signature
    st.success("Google Calendar follow-up reminder created.")
    st.json(event_result)


def run_agent_chat_turn(user_input: str) -> None:
    from app.agent_graph import jobcopilot_agent_graph

    result = jobcopilot_agent_graph.invoke(
        {"messages": [HumanMessage(content=user_input)]},
        config={"configurable": {"thread_id": st.session_state["agent_thread_id"]}},
    )

    st.session_state["agent_messages"] = result["messages"]


def reset_agent_chat() -> None:
    st.session_state["agent_messages"] = []
    st.session_state["agent_thread_id"] = f"agent-chat-{uuid4()}"
    st.success("Agent chat reset.")


def render_saved_applications() -> None:
    records = load_application_records()

    if not records:
        st.info("No saved applications yet.")
        return

    st.metric("Saved applications", len(records))

    for i, record in enumerate(reversed(records), start=1):
        with st.expander(f"{i}. {record.company} — {record.role} [{record.status}]"):
            st.write(f"**Created at:** {record.created_at}")
            st.write(f"**Source:** {record.source}")
            if record.reminder_date:
                st.write(f"**Reminder date:** {record.reminder_date}")
            if record.email_subject:
                st.write(f"**Email subject:** {record.email_subject}")
            if record.notes:
                st.write(f"**Notes:** {record.notes}")


def render_job_analysis_tab(results: dict | None) -> None:
    if not results:
        st.info("No analysis yet.")
        return

    job_analysis = results["job_analysis"]

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Required skills", len(job_analysis["required_skills"]))
    m2.metric("Preferred skills", len(job_analysis["preferred_skills"]))
    m3.metric("Tools / stack", len(job_analysis["tools_and_stack"]))
    m4.metric("Domains", len(job_analysis["domain_focus"]))

    st.subheader("Quick highlights")
    st.write(f"**Company:** {job_analysis['company']}")
    st.write(f"**Role:** {job_analysis['role']}")
    st.write(f"**Location:** {job_analysis['location']}")
    st.write(f"**Contract type:** {job_analysis['contract_type']}")
    st.write(f"**Start date:** {job_analysis['start_date']}")

    with st.expander("Structured job analysis JSON"):
        st.json(job_analysis)


def render_match_tab(results: dict | None) -> None:
    if not results:
        st.info("No match insight yet.")
        return

    match = results["match"]
    memories = results["retrieved_memories"]

    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("Retrieved profile memories")
        for i, memory in enumerate(memories, start=1):
            st.markdown(f"**{i}.** {memory}")

    with col2:
        st.subheader("Strengths")
        for item in match["strengths"]:
            st.markdown(f"- {item}")

        st.subheader("Gaps")
        for item in match["gaps"]:
            st.markdown(f"- {item}")

        st.subheader("Suggested angles")
        for item in match["suggested_angles"]:
            st.markdown(f"- {item}")

    with st.expander("Raw match insight JSON"):
        st.json(match)


def render_email_tab(results: dict | None) -> None:
    if not results:
        st.info("No email draft yet.")
        return

    email_draft = results["email_draft"]

    st.caption(f"Generated tone: {email_draft['tone']}")

    col1, col2 = st.columns([1, 1])

    with col1:
        st.text_input(
            "Recipient email",
            key="recipient_email",
            placeholder="recruiter@company.com",
        )
        st.date_input(
            "Follow-up date",
            key="followup_date",
            min_value=date.today(),
        )

    with col2:
        st.text_input(
            "Email subject",
            key="editable_email_subject",
        )

    st.text_area(
        "Email body",
        key="editable_email_body",
        height=420,
    )

    c1, c2, c3 = st.columns(3)

    with c1:
        if st.button("Create Gmail draft", use_container_width=True):
            try:
                create_current_gmail_draft()
            except Exception as e:
                st.exception(e)

    with c2:
        if st.button("Create follow-up reminder", use_container_width=True):
            try:
                create_current_followup_reminder()
            except Exception as e:
                st.exception(e)

    with c3:
        if st.button("Save application record", use_container_width=True):
            try:
                save_current_application()
            except Exception as e:
                st.exception(e)


def render_saved_applications_tab() -> None:
    st.subheader("Saved applications")
    render_saved_applications()


def render_agent_chat_tab() -> None:
    st.subheader("Agent Chat")
    st.caption(
        "Ask the agent to analyze a job, create a Gmail draft, save an application, or schedule a follow-up reminder."
    )

    col1, col2 = st.columns([4, 1])
    with col2:
        if st.button("Reset chat", use_container_width=True):
            reset_agent_chat()

    messages = st.session_state.get("agent_messages", [])

    if not messages:
        st.info(
            "No agent interaction yet. Example: 'Analyze this job offer and draft an email for me.'"
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
            with st.expander("Tool output"):
                st.code(_message_to_text(message.content))

    user_input = st.chat_input("Ask JobCopilot agent...")

    if user_input:
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.spinner("Agent is thinking..."):
            try:
                run_agent_chat_turn(user_input)
                st.rerun()
            except Exception as e:
                st.exception(e)


def main() -> None:
    st.set_page_config(
        page_title="JobCopilot",
        page_icon="📨",
        layout="wide",
    )

    initialize_session_state()

    st.title("📨 JobCopilot")
    st.caption(
        "Analyze a job offer, match it against your profile memory, generate a tailored application email, create a Gmail draft, schedule a follow-up reminder, and interact with an agent."
    )

    with st.sidebar:
        st.header("Pipeline")
        st.write("1. Analyze job")
        st.write("2. Retrieve profile memory")
        st.write("3. Generate match insight")
        st.write("4. Draft tailored email")
        st.write("5. Gmail + Calendar + Save")
        st.write("6. Agent Chat")

        results = st.session_state.get("results")
        if results:
            st.divider()
            job_analysis = results["job_analysis"]
            st.write("**Current job**")
            st.write(job_analysis["company"])
            st.write(job_analysis["role"])

    job_text = st.text_area(
        "Paste the job offer here",
        value=DEFAULT_JOB_TEXT,
        height=320,
    )

    if st.button("Analyze job", type="primary", use_container_width=True):
        if not job_text.strip():
            st.warning("Please paste a job offer first.")
        else:
            with st.spinner("Running JobCopilot pipeline..."):
                try:
                    st.session_state["results"] = run_pipeline(job_text)
                    sync_editable_email_fields()
                    st.session_state["last_gmail_draft_signature"] = ""
                    st.session_state["last_calendar_signature"] = ""
                    st.success("Analysis completed.")
                except Exception as e:
                    st.exception(e)

    results = st.session_state.get("results")

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        [
            "Job Analysis",
            "Match Insight",
            "Email Draft",
            "Saved Applications",
            "Agent Chat",
        ]
    )

    with tab1:
        render_job_analysis_tab(results)

    with tab2:
        render_match_tab(results)

    with tab3:
        render_email_tab(results)

    with tab4:
        render_saved_applications_tab()

    with tab5:
        render_agent_chat_tab()


if __name__ == "__main__":
    main()