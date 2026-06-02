from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig

from core_setup.llm import structured_invoke

from memory.ltm.context import build_memory_context

from schemas import Plan
from state import AgentState


def build_tool_context(tools: list) -> str:
    """
    Convert registered tools into a planner-friendly list.
    """

    lines = []

    for tool in tools:
        name = getattr(tool, "name", str(tool))

        description = getattr(
            tool,
            "description",
            "No description available.",
        )

        lines.append(
            f"- {name}: {description}"
        )

    return "\n".join(lines)


async def planner_node(
    state: AgentState,
    config: RunnableConfig,
):
    user_id = (
        config.get("configurable", {})
        .get("user_id", "default_user")
    )

    memory_context = build_memory_context(user_id)

    available_tools = config["configurable"]["tools"]

    tool_context = build_tool_context(
        available_tools
    )

    planner_prompt = SystemMessage(
        content=f"""
You are the Planner Node.

Your job is ONLY to create a plan.

DO NOT execute anything.

Available tools:

{tool_context}

Rules:

- Use exact tool names.
- Only choose tools that exist.
- If no tool is required, return empty plan and empty tools list.
- Keep plans short and actionable.
"""
    )

    memory_message = SystemMessage(
        content=f"""
Known User Information:

{memory_context}
"""
    )

    result = await structured_invoke(
        messages=[
            planner_prompt,
            memory_message,
            *state["messages"],
        ],
        schema=Plan,
    )

    if result is None:
        return {
            "error": "Planner failed.",
            "plan": [],
            "planned_tools": [],
        }

    return {
        "plan": result.plan,
        "planned_tools": result.tools,
        "memory_context": memory_context,
        "error": None,
    }