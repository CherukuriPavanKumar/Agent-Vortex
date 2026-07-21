from langgraph.types import interrupt

from state import AgentState


def approval_node(
    state: AgentState,
):
    """
    Pause execution and ask
    the user to approve the plan.
    """

    approval_result = interrupt(
        {
            "plan": state.get(
                "plan",
                [],
            ),
            "planned_tools": state.get(
                "planned_tools",
                [],
            ),
            "risk_level": state.get(
                "risk_level",
                "low",
            ),
        }
    )

    return {
        "approved": bool(
            approval_result
        )
    }