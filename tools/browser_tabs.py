from langchain.tools import tool
from core_setup.mcp_client import call_browser_tool


@tool
async def browser_tabs(action: str, tab_id: str | None = None):
    """
    Manage browser tabs.
    Actions:
    - "list": List all open tabs
    - "create": Create a new tab
    - "switch": Switch to tab by tab_id
    - "close": Close tab by tab_id
    """
    try:
        args = {"action": action}
        if tab_id:
            args["tabId"] = tab_id

        result = await call_browser_tool("browser_tabs", args)
        return result.content[0].text if result.content else f"Tab {action} completed."
    except Exception as e:
        return f"Tabs error: {str(e)}"
