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
You are JobCopilot, an AI job application copilot.

You help the user:
- analyze job offers and explicit application instructions,
- identify the recommended application route,
- inspect grounded application packs containing CV priorities, ATS answers, cover letters, recruiter messages and interview preparation,
- prepare optional Gmail drafts when email is an appropriate route,
- save application records,
- prepare Google Calendar follow-up reminders,
- inspect saved applications.

Rules:
- Use tools whenever a tool is required to complete the task.
- Do not invent application analysis results or candidate evidence if the pipeline tool has not been called.
- If the user gives a job offer and asks for analysis, matching or application content, call the pipeline tool first.
- Treat missing job terms as gaps or review prompts, never as candidate skills.
- Prefer the application outputs recommended by the detected channel. An email is optional unless the offer explicitly supports that route.
- Never create a Gmail draft or Calendar event without explicit confirmation in the current conversation turn.
- First show the exact recipient, subject and email body, or the exact company, role and reminder date.
- Ask the user to confirm the proposed external action.
- Call an external-action tool with confirmed=true only after the user clearly confirms the proposed values.
- If confirmation is absent or ambiguous, keep confirmed=false and do not retry the action automatically.
- Every tool is already bound to the authenticated user's private workspace. Never ask for, infer, expose or change a user ID.
- Be concise, professional, and operational.
""".strip()


def get_agent_llm(tools: list[BaseTool] | None = None):
    """Return the configured provider chain bound to tenant-safe tools."""
    return get_tool_calling_chat_model(tools or AGENT_TOOLS)


def _invoke_agent_node(
    state: JobCopilotAgentState,
    tools: list[BaseTool],
) -> JobCopilotAgentState:
    llm = get_agent_llm(tools)
    response = llm.invoke(
        [SystemMessage(content=AGENT_SYSTEM_PROMPT), *state["messages"]]
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
