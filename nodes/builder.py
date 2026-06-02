from typing import Any

from langgraph.graph import (
    StateGraph,
    START,
    END,
)

from langgraph.prebuilt import (
    ToolNode,
    tools_condition,
)

from state import AgentState

from nodes.planner import planner_node
from nodes.risk import (
    risk_node,
    route_after_risk,
    auto_approve_node,
)
from nodes.approval import approval_node
from nodes.executor import executor_node


# ------------------------------------------------------------------
# Routing
# ------------------------------------------------------------------


def route_after_planner(state: AgentState) -> str:
    """
    Planner outcomes:

    1. Planner failed
       -> END

    2. Planner created a plan
       -> Risk assessment

    3. No plan needed
       -> Executor (normal chat response)
    """

    if state.get("error"):
        return END

    if state.get("plan"):
        return "risk"

    return "executor"


# ------------------------------------------------------------------
# Graph Builder
# ------------------------------------------------------------------


def build_graph(
    tools: list[Any],
    checkpointer=None,
):
    """
    Build the Agent Vortex workflow graph.

    Flow:

        START
          ↓
       Planner
          ↓
         Risk
          ↓
      Approval?
          ↓
       Executor
          ↓
        Tools
          ↓
       Executor
          ↓
          END

    The executor/tool loop continues until no more tool calls
    are produced.
    """

    tool_node = ToolNode(tools)

    graph = StateGraph(AgentState)

    # --------------------------------------------------------------
    # Nodes
    # --------------------------------------------------------------

    graph.add_node("planner",planner_node)

    graph.add_node("risk",risk_node)

    graph.add_node("auto_approve",auto_approve_node)

    graph.add_node("approval",approval_node)

    graph.add_node("executor",executor_node)

    graph.add_node("tools",tool_node)

    # --------------------------------------------------------------
    # Entry
    # --------------------------------------------------------------

    graph.add_edge(START,"planner")

    # --------------------------------------------------------------
    # Planner Routing
    # --------------------------------------------------------------

    graph.add_conditional_edges("planner",route_after_planner)

    # --------------------------------------------------------------
    # Risk Routing
    # --------------------------------------------------------------

    graph.add_conditional_edges("risk",route_after_risk)

    # --------------------------------------------------------------
    # Approval Paths
    # --------------------------------------------------------------

    graph.add_edge("auto_approve","executor")

    graph.add_edge("approval","executor")

    # --------------------------------------------------------------
    # Tool Execution Loop
    # --------------------------------------------------------------

    graph.add_conditional_edges("executor",tools_condition)

    graph.add_edge("tools","executor")

    # --------------------------------------------------------------
    # Compile
    # --------------------------------------------------------------

    return graph.compile(
        checkpointer=checkpointer,
    )