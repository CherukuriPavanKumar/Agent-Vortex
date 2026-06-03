from langchain.tools import tool
from core_setup.mcp_client import call_browser_tool


@tool
async def browser_tabs(action: str, tab_id: str | None = None):
    """
    Manage browser tabs in the real Chromium browser session.

    USE THIS TOOL to:
    - Open a new browser tab for a second website
    - Switch between open browser tabs
    - List all currently open browser tabs
    - Close a browser tab

    NEVER use terminal_tool for tab management.

    Actions:
    - "list": List all open tabs and their IDs
    - "create": Open a new empty browser tab
    - "switch": Switch to a specific tab by tab_id
    - "close": Close a tab by tab_id
    """
    try:
        args = {"action": action}
        if tab_id:
            args["tabId"] = tab_id

        result = await call_browser_tool("browser_tabs", args)
        return result.content[0].text if result.content else f"Tab {action} completed."
    except Exception as e:
        return f"Tabs error: {str(e)}"
