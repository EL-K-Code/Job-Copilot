from __future__ import annotations

from functools import lru_cache

from langchain_core.messages import SystemMessage
from langchain_core.tools import BaseTool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import START, END, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from app.agent_state import JobCopilotAgentState
from app.agent_tools import AGENT_TOOLS, build_agent_tools
from app.config import settings
from app.services.model_provider import get_tool_calling_chat_model
from app.services.usage_quota import consume_ai_operation
from app.tenancy import normalize_user_id


AGENT_SYSTEM_PROMPT = """
You are JobCopilot, an evidence-grounded, human-supervised job application copilot.

You help the user:
- analyze job offers and explicit application instructions,
- identify the recommended application route,
- inspect grounded application packs containing CV priorities, ATS answers, cover letters, recruiter messages and interview preparation,
- manage the deterministic application lifecycle,
- inspect saved applications and follow-ups.

Application lifecycle:
DISCOVERED -> ANALYZED -> READY_TO_APPLY -> AWAITING_APPROVAL -> APPLIED
APPLIED may become FOLLOW_UP_DUE, INTERVIEW, REJECTED, OFFER or CLOSED.
FOLLOW_UP_DUE and INTERVIEW may later become INTERVIEW, REJECTED, OFFER or CLOSED as allowed by the workflow tool.

Lifecycle rules:
- Run the pipeline before claiming that an offer has been analyzed or matched.
- Pipeline analysis itself is read-only with respect to the tracker.
- Save an application only when the user asks to track or continue it.
- A saved draft is treated as READY_TO_APPLY for backward compatibility.
- Move READY_TO_APPLY to AWAITING_APPROVAL before recording the application as submitted.
- Never mark an application APPLIED unless the user explicitly confirms it was actually submitted or sent.
- Never infer INTERVIEW, REJECTED or OFFER from silence, elapsed time, or model reasoning; only record a user-reported outcome after confirmation.
- FOLLOW_UP_DUE can be derived deterministically from an applied application's reminder date.
- Use workflow inspection tools before changing lifecycle state when the current stage is unclear.

Grounding rules:
- Use tools whenever a tool is required to complete the task.
- Do not invent application analysis results or candidate evidence if the pipeline tool has not been called.
- If the user gives a job offer and asks for analysis, matching or application content, call the pipeline tool first.
- Treat missing job terms as gaps or review prompts, never as candidate skills.
- Prefer the application outputs recommended by the detected channel. An email is optional unless the offer explicitly supports that route.
- Every tool is already bound to the authenticated user's private workspace. Never ask for, infer, expose or change a user ID.
- Be concise, professional, and operational.
""".strip()


GOOGLE_ACTION_RULES = """
This deployment also exposes optional Google actions when the user has connected Google:
- prepare Gmail drafts when email is an appropriate route,
- prepare Google Calendar follow-up reminders.

External-action rules:
- Never create a Gmail draft or Calendar event without explicit confirmation in the current conversation turn.
- First show the exact recipient, subject and email body, or the exact company, role and reminder date.
- Ask the user to confirm the proposed external action.
- Call an external-action tool with confirmed=true only after the user clearly confirms the proposed values.
- If confirmation is absent or ambiguous, keep confirmed=false and do not retry the action automatically.
- When a saved workflow exists, provide company and role to Gmail actions so successful side effects can be idempotently audited.
- A Gmail draft is not proof that an application was sent. Do not mark APPLIED because a draft was created.
- A Calendar event is not proof that a follow-up was sent. It only schedules a reminder.
- If Google is not connected, explain that the user must connect it from Settings; do not claim an external action succeeded.
""".strip()


HOSTED_DEMO_RULES = """
Hosted recruiter demo boundary:
- Gmail and Google Calendar actions are intentionally unavailable in this deployment.
- Do not claim that you can connect Google, create Gmail drafts or create Calendar events.
- You may still analyze roles, build grounded application content, manage the supervised application lifecycle and inspect the tracker.
""".strip()


def _system_prompt() -> str:
    """Return a prompt that matches the tools exposed by this deployment."""
    google_available = (
        not settings.hosted_recruiter_demo
        or bool(getattr(settings, "hosted_google_oauth_enabled", False))
    )
    boundary = GOOGLE_ACTION_RULES if google_available else HOSTED_DEMO_RULES
    return f"{AGENT_SYSTEM_PROMPT}\n\n{boundary}"


def get_agent_llm(tools: list[BaseTool] | None = None):
    """Return the configured provider chain bound to tenant-safe tools."""
    return get_tool_calling_chat_model(tools or AGENT_TOOLS)


def _invoke_agent_node(
    state: JobCopilotAgentState,
    tools: list[BaseTool],
) -> JobCopilotAgentState:
    llm = get_agent_llm(tools)
    response = llm.invoke(
        [SystemMessage(content=_system_prompt()), *state["messages"]]
    )
    return {"messages": [response]}


def agent_node(state: JobCopilotAgentState) -> JobCopilotAgentState:
    """Backward-compatible single-user agent node."""
    return _invoke_agent_node(state, AGENT_TOOLS)


def build_jobcopilot_agent_graph(user_id: str | None = None):
    """
    Build an agent graph whose tools and in-memory checkpoint are isolated to one user.

    A separate graph instance is required because LangGraph's in-memory checkpointer holds
    conversation state. Sharing it across tenants would make a thread-ID collision a data
    isolation risk.
    """
    normalized_user_id = (
        normalize_user_id(user_id) if user_id is not None else None
    )
    tools = build_agent_tools(normalized_user_id)

    def scoped_agent_node(state: JobCopilotAgentState) -> JobCopilotAgentState:
        return _invoke_agent_node(state, tools)

    builder = StateGraph(JobCopilotAgentState)
    builder.add_node("agent", scoped_agent_node)
    builder.add_node("tools", ToolNode(tools))

    if normalized_user_id is not None and settings.beta_auth_enabled:
        def quota_node(_state: JobCopilotAgentState) -> JobCopilotAgentState:
            consume_ai_operation(normalized_user_id, "agent_chat")
            return {}

        builder.add_node("quota", quota_node)
        builder.add_edge(START, "quota")
        builder.add_edge("quota", "agent")
    else:
        builder.add_edge(START, "agent")

    builder.add_conditional_edges(
        "agent",
        tools_condition,
        {
            "tools": "tools",
            "__end__": END,
        },
    )
    builder.add_edge("tools", "agent")

    return builder.compile(checkpointer=InMemorySaver())


@lru_cache(maxsize=64)
def get_jobcopilot_agent_graph(user_id: str):
    """Return one cached agent graph and checkpointer per normalized beta user."""
    return build_jobcopilot_agent_graph(normalize_user_id(user_id))


def clear_jobcopilot_agent_graph_cache() -> None:
    """Clear all tenant-scoped in-memory agent graphs and conversations."""
    get_jobcopilot_agent_graph.cache_clear()


# Backward-compatible graph used by non-tenant command-line callers.
jobcopilot_agent_graph = build_jobcopilot_agent_graph()
