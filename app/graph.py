from __future__ import annotations

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import START, END, StateGraph

from app.memory import retrieve_profile_context
from app.services.llm import (
    analyze_job_offer,
    generate_match_insight,
    generate_application_email_draft,
)
from app.state import JobCopilotState


def analyze_job_node(state: JobCopilotState) -> JobCopilotState:
    job_text = state["job_text"]
    job_analysis = analyze_job_offer(job_text)

    retrieval_query = (
        f"{job_analysis.role}. "
        f"Required skills: {', '.join(job_analysis.required_skills)}. "
        f"Tools and stack: {', '.join(job_analysis.tools_and_stack)}. "
        f"Domain focus: {', '.join(job_analysis.domain_focus)}."
    )

    return {
        "job_analysis": job_analysis.model_dump(),
        "retrieval_query": retrieval_query,
    }


def retrieve_memory_node(state: JobCopilotState) -> JobCopilotState:
    query = state["retrieval_query"]
    docs = retrieve_profile_context(query, k=5)
    retrieved_memories = [doc.page_content for doc in docs]

    return {
        "retrieved_memories": retrieved_memories,
    }


def generate_match_node(state: JobCopilotState) -> JobCopilotState:
    from app.schemas import JobAnalysis

    job_analysis = JobAnalysis(**state["job_analysis"])
    retrieved_memories = state["retrieved_memories"]

    match = generate_match_insight(
        job_analysis=job_analysis,
        retrieved_profile_memories=retrieved_memories,
    )

    return {
        "match_insight": match.model_dump(),
    }


def generate_email_node(state: JobCopilotState) -> JobCopilotState:
    from app.schemas import JobAnalysis, MatchInsight

    job_analysis = JobAnalysis(**state["job_analysis"])
    match_insight = MatchInsight(**state["match_insight"])

    email_draft = generate_application_email_draft(
        job_analysis=job_analysis,
        match_insight=match_insight,
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

    checkpointer = InMemorySaver()
    return builder.compile(checkpointer=checkpointer)


jobcopilot_graph = build_jobcopilot_graph()