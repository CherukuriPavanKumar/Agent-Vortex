from typing import TypedDict, Annotated
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]

    plan: list[str]
    planned_tools: list[str]

    risk_level: str

    approved: bool

    memory_context: str

    error: str | None