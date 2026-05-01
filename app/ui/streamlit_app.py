from __future__ import annotations
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st

from app.memory import retrieve_profile_context
from app.services.llm import (
    analyze_job_offer,
    generate_match_insight,
    generate_application_email_draft,
)
from app.services.applications_store import (
    create_application_record,
    add_application_record,
    load_application_records,
)


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


def run_pipeline(job_text: str) -> dict:
    job_analysis = analyze_job_offer(job_text)

    query = (
        f"{job_analysis.role}. "
        f"Required skills: {', '.join(job_analysis.required_skills)}. "
        f"Tools and stack: {', '.join(job_analysis.tools_and_stack)}. "
        f"Domain focus: {', '.join(job_analysis.domain_focus)}."
    )

    docs = retrieve_profile_context(query, k=5)
    retrieved_memories = [doc.page_content for doc in docs]

    match = generate_match_insight(
        job_analysis=job_analysis,
        retrieved_profile_memories=retrieved_memories,
    )

    email_draft = generate_application_email_draft(
        job_analysis=job_analysis,
        match_insight=match,
    )

    return {
        "job_analysis": job_analysis,
        "retrieved_memories": retrieved_memories,
        "match": match,
        "email_draft": email_draft,
    }


def save_current_application() -> None:
    results = st.session_state.get("results")
    if not results:
        st.warning("No analyzed application to save yet.")
        return

    job_analysis = results["job_analysis"]
    email_draft = results["email_draft"]

    record = create_application_record(
        company=job_analysis.company,
        role=job_analysis.role,
        email_subject=email_draft.subject,
        email_body=email_draft.body,
        status="drafted",
        source="streamlit",
        notes="Saved from Streamlit UI.",
    )
    add_application_record(record)
    st.success("Application record saved.")


def render_saved_applications() -> None:
    records = load_application_records()

    st.subheader("Saved applications")

    if not records:
        st.info("No saved applications yet.")
        return

    for i, record in enumerate(reversed(records), start=1):
        with st.expander(f"{i}. {record.company} — {record.role} [{record.status}]"):
            st.write(f"**Created at:** {record.created_at}")
            st.write(f"**Source:** {record.source}")
            if record.email_subject:
                st.write(f"**Email subject:** {record.email_subject}")
            if record.notes:
                st.write(f"**Notes:** {record.notes}")


def main() -> None:
    st.set_page_config(
        page_title="JobCopilot",
        page_icon="📨",
        layout="wide",
    )

    st.title("📨 JobCopilot")
    st.caption(
        "Analyze a job offer, match it against your profile memory, and generate a tailored application email."
    )

    if "results" not in st.session_state:
        st.session_state["results"] = None

    with st.sidebar:
        st.header("Actions")
        analyze_clicked = st.button("Analyze job", use_container_width=True)
        save_clicked = st.button("Save application record", use_container_width=True)

    job_text = st.text_area(
        "Paste the job offer here",
        value=DEFAULT_JOB_TEXT,
        height=320,
    )

    if analyze_clicked:
        if not job_text.strip():
            st.warning("Please paste a job offer first.")
        else:
            with st.spinner("Running JobCopilot pipeline..."):
                try:
                    st.session_state["results"] = run_pipeline(job_text)
                    st.success("Analysis completed.")
                except Exception as e:
                    st.exception(e)

    if save_clicked:
        try:
            save_current_application()
        except Exception as e:
            st.exception(e)

    results = st.session_state.get("results")

    left, right = st.columns([1, 1])

    with left:
        st.subheader("Job analysis")
        if results:
            st.json(results["job_analysis"].model_dump())
        else:
            st.info("No analysis yet.")

        st.subheader("Retrieved profile memories")
        if results:
            for i, memory in enumerate(results["retrieved_memories"], start=1):
                st.markdown(f"**{i}.** {memory}")
        else:
            st.info("No memories retrieved yet.")

        st.subheader("Match insight")
        if results:
            st.json(results["match"].model_dump())
        else:
            st.info("No match insight yet.")

    with right:
        st.subheader("Email draft")
        if results:
            email_draft = results["email_draft"]
            st.text_input("Subject", value=email_draft.subject, disabled=True)
            st.text_area("Body", value=email_draft.body, height=420, disabled=True)
            st.caption(f"Tone: {email_draft.tone}")
        else:
            st.info("No email draft yet.")

    st.divider()
    render_saved_applications()


if __name__ == "__main__":
    main()