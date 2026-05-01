from __future__ import annotations

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import START, END, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from app.agent_state import JobCopilotAgentState
from app.agent_tools import AGENT_TOOLS
from app.config import settings


AGENT_SYSTEM_PROMPT = """
You are JobCopilot, an AI job application copilot.

You help the user:
- analyze job offers,
- retrieve structured application results,
- create Gmail drafts,
- save application records,
- create Google Calendar follow-up reminders,
- inspect saved applications.

Rules:
- Use tools whenever a tool is required to complete the task.
- Do not invent application analysis results if the pipeline tool has not been called.
- If the user gives a job offer and asks for analysis or an email, call the pipeline tool first.
- If the user asks for a Gmail draft, ensure you have a subject and body before calling the Gmail tool.
- If the user asks for a follow-up reminder, ensure you have company, role, and a date before calling the Calendar tool.
- Be concise, professional, and operational.
""".strip()


def get_agent_llm() -> ChatAnthropic:
    return ChatAnthropic(
        model=settings.anthropic_model,
        temperature=0,
        api_key=settings.anthropic_api_key,
    ).bind_tools(AGENT_TOOLS)


def agent_node(state: JobCopilotAgentState) -> JobCopilotAgentState:
    llm = get_agent_llm()

    response = llm.invoke(
        [SystemMessage(content=AGENT_SYSTEM_PROMPT), *state["messages"]]
    )

    return {"messages": [response]}


def build_jobcopilot_agent_graph():
    builder = StateGraph(JobCopilotAgentState)

    builder.add_node("agent", agent_node)
    builder.add_node("tools", ToolNode(AGENT_TOOLS))

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

    checkpointer = InMemorySaver()
    return builder.compile(checkpointer=checkpointer)


jobcopilot_agent_graph = build_jobcopilot_agent_graph()