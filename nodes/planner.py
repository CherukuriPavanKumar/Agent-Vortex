from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig

from core_setup.llm import structured_invoke
from core_setup.tools import build_tool_context

from memory.ltm.context import build_memory_context

from schemas import Plan
from state import AgentState



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

Your job is ONLY to create a plan. DO NOT execute anything.
IMPORTANT: You have access to past conversation history and long-term user preferences (which are injected into your context). Do NOT claim that you lack access to past conversations or personal information. Use the context provided to you.

Available tools:

{tool_context}

========================================
TOOL ROUTING RULES
========================================

RULE 1 — WEB / URL TASKS (HIGHEST PRIORITY):

If the user request contains any of the following:
  - A URL (http://, https://)
  - Words: website, webpage, browse, navigate, open site,
    click, online, news, article, read page, web

Then you MUST produce a plan using ONLY browser tools:
  Step 1: browser_navigate -- open the URL or website
  Step 2: browser_read -- read and extract the page content
  Step 3: (optional) browser_interaction -- only if clicking/typing needed

NEVER plan terminal_tool, curl, wget, lynx, or any shell command for web tasks.

CORRECT example plan for "open https://news.ycombinator.com and get top 5 stories":
  1. Open https://news.ycombinator.com using browser_navigate
  2. Read page content using browser_read
  3. Extract and summarize the first 5 story titles from the content

WRONG example plan (NEVER do this):
  1. Run curl https://news.ycombinator.com using terminal_tool

RULE 2 — FILESYSTEM / SYSTEM TASKS:

If the user request involves local files, shell commands, code execution,
package installation, or git operations:
  Use terminal_tool.
  Do NOT use browser tools for local system tasks.

RULE 3 — EMAIL / CALENDAR TASKS:

Use gmail_read, gmail_send, calendar_read, calendar_write only for
Google Workspace tasks. Do not use browser tools for these.

========================================
GENERAL PLANNING RULES
========================================

- Use exact tool names from the available tools list above.
- Only choose tools that exist in the list.
- If no tool is required, return an empty plan and empty tools list.
- Keep plans short and actionable (3-5 steps max).
- Plans describe WHAT to do, not HOW the tool works internally.
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