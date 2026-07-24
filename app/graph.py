from __future__ import annotations

from langgraph.graph import START, END, StateGraph

from app.memory import retrieve_profile_context
from app.services.llm import (
    analyze_job_offer,
    generate_match_insight,
    generate_application_email_draft,
)
from app.state import JobCopilotState


_EMAIL_RETRIEVAL_K = 8


def analyze_job_node(state: JobCopilotState) -> JobCopilotState:
    job_text = state["job_text"]
    job_analysis = analyze_job_offer(job_text)

    retrieval_query = (
        f"{job_analysis.role}. "
        f"Missions: {', '.join(job_analysis.missions_summary)}. "
        f"Required skills: {', '.join(job_analysis.required_skills)}. "
        f"Preferred skills: {', '.join(job_analysis.preferred_skills)}. "
        f"Tools and stack: {', '.join(job_analysis.tools_and_stack)}. "
        f"Domain focus: {', '.join(job_analysis.domain_focus)}."
    )

    return {
        "job_analysis": job_analysis.model_dump(),
        "retrieval_query": retrieval_query,
    }


def retrieve_memory_node(state: JobCopilotState) -> JobCopilotState:
    query = state["retrieval_query"]
    docs = retrieve_profile_context(query, k=_EMAIL_RETRIEVAL_K)
    retrieved_memory_records = [
        {
            "id": str(doc.metadata.get("id", "")).strip(),
            "type": str(doc.metadata.get("type", "unknown")).strip() or "unknown",
            "content": doc.page_content,
        }
        for doc in docs
    ]
    retrieved_memories = [record["content"] for record in retrieved_memory_records]

    return {
        "retrieved_memories": retrieved_memories,
        "retrieved_memory_records": retrieved_memory_records,
    }


def generate_match_node(state: JobCopilotState) -> JobCopilotState:
    from app.schemas import JobAnalysis

    job_analysis = JobAnalysis(**state["job_analysis"])
    retrieved_memory_records = state["retrieved_memory_records"]

    match = generate_match_insight(
        job_analysis=job_analysis,
        retrieved_profile_memories=retrieved_memory_records,
    )

    return {
        "match_insight": match.model_dump(),
    }


def generate_email_node(state: JobCopilotState) -> JobCopilotState:
    from app.schemas import JobAnalysis, MatchInsight

    job_analysis = JobAnalysis(**state["job_analysis"])
    match_insight = MatchInsight(**state["match_insight"])
    retrieved_memory_records = state["retrieved_memory_records"]

    email_draft = generate_application_email_draft(
        job_analysis=job_analysis,
        match_insight=match_insight,
        retrieved_profile_memories=retrieved_memory_records,
    )

    return {
        "email_draft": email_draft.model_dump(),
    }


def build_jobcopilot_graph():
    builder = StateGraph(JobCopilotState)

    builder.add_node("analyze_job", analyze_job_node)
    builder.add_node("retrieve_memory", retrieve_memory_node)
    builder.add_node("generate_match", generate_match_node)
    builder.add_node("generate_email", generate_email_node)

    builder.add_edge(START, "analyze_job")
    builder.add_edge("analyze_job", "retrieve_memory")
    builder.add_edge("retrieve_memory", "generate_match")
    builder.add_edge("generate_match", "generate_email")
    builder.add_edge("generate_email", END)

    # The deterministic pipeline is stateless. Compiling it without a shared
    # checkpointer prevents cross-session state from being retained or mixed.
    return builder.compile()


jobcopilot_graph = build_jobcopilot_graph()
