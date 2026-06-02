from langchain_core.messages import (
    SystemMessage,
    AIMessage,
)

from state import AgentState
from core_setup.llm import invoke

EXECUTOR_PROMPT = SystemMessage(
    content="""
You are the Executor Node.

Your responsibility is to execute the plan.

Rules:

- If a tool is required, call it.
- Never claim a task succeeded unless a tool returned success.
- Never invent tool outputs.
- If a tool fails, explain the failure.
- Be concise.
"""
)

async def executor_node(
    state: AgentState,
    config,
):
    """
    Execute plan using tools.
    """

    if state.get("plan") and not state.get(
        "approved",
        False,
    ):
        return {
            "messages": [
                AIMessage(
                    content=(
                        "Plan cancelled."
                    )
                )
            ]
        }

    messages = [
        EXECUTOR_PROMPT,
        *state["messages"],
    ]

    memory_context = state.get("memory_context")
    if memory_context:
        messages.insert(
            1,
            SystemMessage(
                content=f"""
Known User Information:

{memory_context}
"""
            )
        )

    tools = config[
        "configurable"
    ]["tools"]

    if state["plan"]:

        plan_text = "\n".join(
        f"{i+1}. {step}"
        for i, step
        in enumerate(
            state["plan"]
        )
    )

        messages.insert(
            2 if memory_context else 1,
            SystemMessage(
            content=f"""
Approved Plan:

{plan_text}

Execute it.
"""
            )
        )

    response = await invoke(
        messages=messages,
        tools=tools,
    )

    return {
        "messages": [response]
    }

