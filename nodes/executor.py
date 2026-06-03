from langchain_core.messages import (
    SystemMessage,
    AIMessage,
)

from state import AgentState
from core_setup.llm import invoke

# Browser-related keyword triggers for routing validation
_WEB_KEYWORDS = {
    "http://", "https://", "www.", "website", "webpage",
    "browse", "navigate", "open site", "click", "url",
    "news", "article", "online", "web",
}

_BROWSER_TOOLS = {
    "browser_navigate", "browser_read",
    "browser_interaction", "browser_tabs",
}

EXECUTOR_PROMPT = SystemMessage(
    content="""
You are the Executor Node.

Your responsibility is to execute the approved plan using the available tools.

\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501
BROWSER-FIRST RULE (HIGHEST PRIORITY)
\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501

When the task involves ANY of the following:
  - A URL (http://, https://)
  - A website, webpage, web app
  - Browsing, navigating, opening a site
  - Reading online content, news, articles, documentation
  - Clicking, typing, submitting forms on the web
  - Screenshots of websites
  - Any online resource

You MUST use browser tools in this exact sequence:
  1. browser_navigate(url="...") -- to open the website
  2. browser_read()              -- to read/extract the page content
  3. browser_interaction(...)    -- ONLY if clicking or typing is needed

You are STRICTLY FORBIDDEN from using terminal_tool for web access.
The following shell commands are PROHIBITED when browser tools are available:
  NO: curl
  NO: wget
  NO: lynx
  NO: chromium-browser <url>
  NO: playwright <command>
  NO: npx playwright
  NO: python -c "import requests..."
  NO: Any shell-based HTTP fetch

\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501
TERMINAL TOOL SCOPE
\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501

terminal_tool is ONLY for:
  OK: Filesystem operations (ls, cat, cp, mv, mkdir)
  OK: Local code execution (python script.py)
  OK: Package management (pip install, apt install)
  OK: Git operations (git status, git commit)
  OK: System inspection (ps, df, top)

terminal_tool must NEVER be used to access URLs or websites.

\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501
GENERAL EXECUTION RULES
\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501

- If a tool is required, call it. Do not simulate results.
- Never claim a task succeeded unless a tool returned success.
- Never invent tool outputs.
- If a tool fails, report the exact error. Do not retry with terminal_tool.
- Be concise in final answers.
"""
)


def _log_tool_selection(tools: list, response, user_text: str = "") -> None:
    """
    Emit a [Tool Selection] debug block showing what the LLM chose.
    """
    available_names = [getattr(t, "name", str(t)) for t in tools]
    browser_available = bool(_BROWSER_TOOLS & set(available_names))

    chosen = []
    if hasattr(response, "tool_calls") and response.tool_calls:
        chosen = [tc["name"] for tc in response.tool_calls]

    print("\n" + "-" * 48)
    print("[Tool Selection]")
    print(f"  Available : {', '.join(available_names)}")
    print(f"  Browser tools present: {browser_available}")
    print(f"  Chosen    : {', '.join(chosen) if chosen else '(none -- text response)'}")

    # Warn if terminal was chosen for a web-looking task
    user_lower = user_text.lower()
    looks_like_web = any(kw in user_lower for kw in _WEB_KEYWORDS)
    if "terminal_tool" in chosen and browser_available and looks_like_web:
        print("  WARNING: terminal_tool selected for a web task -- browser tools were available!")
    elif browser_available and looks_like_web and chosen:
        all_browser = all(c in _BROWSER_TOOLS for c in chosen)
        if all_browser:
            print("  OK: browser tools selected for web task.")

    print("-" * 48 + "\n")


async def executor_node(
    state: AgentState,
    config,
):
    """
    Execute plan using tools, with tool-selection debug logging.
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

    # -------------------------------------------------------
    # Extract last user message text for web-task detection
    # -------------------------------------------------------
    user_text = ""
    for msg in reversed(state["messages"]):
        if hasattr(msg, "content") and isinstance(msg.content, str):
            user_text = msg.content
            break

    response = await invoke(
        messages=messages,
        tools=tools,
    )

    # -------------------------------------------------------
    # Debug: log which tool the model selected
    # -------------------------------------------------------
    _log_tool_selection(tools, response, user_text)

    return {
        "messages": [response]
    }
