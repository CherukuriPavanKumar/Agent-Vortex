from state import AgentState


TOOL_RISK = {
    # High Risk
    "terminal_tool": "high",

    # Medium Risk
    "gmail_send": "medium",
    "whatsapp_send_message": "medium",
    "calendar_write": "medium",
    "browser_interaction": "medium",

    # Low Risk
    "gmail_read": "low",
    "calendar_read": "low",
    "browser_navigate": "low",
    "browser_read": "low",
    "browser_tabs": "low",
    "generate_pdf": "low",
    "generate_excel": "low",
}

RISK_PRIORITY = {
    "low": 0,
    "medium": 1,
    "high": 2,
}

def assess_risk(
    planned_tools: list[str],
) -> str:
    """
    Determine overall risk level
    from planned tools.
    """

    highest_risk = "low"

    for tool in planned_tools:

        tool_risk = TOOL_RISK.get(
            tool,
            "medium",  # unknown tools default upward
        )

        if (
            RISK_PRIORITY[tool_risk]
            > RISK_PRIORITY[highest_risk]
        ):
            highest_risk = tool_risk

    return highest_risk

async def risk_node(
    state: AgentState,
):
    planned_tools = state.get(
        "planned_tools",
        [],
    )

    risk_level = assess_risk(
        planned_tools
    )

    return {
        "risk_level": risk_level
    }

def route_after_risk(
    state: AgentState,
):
    if state["risk_level"] in (
        "medium",
        "high",
    ):
        return "approval"

    return "auto_approve"

def auto_approve_node(
    state: AgentState,
):
    return {
        "approved": True
    }