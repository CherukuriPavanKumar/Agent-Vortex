from langchain.tools import tool
from core_setup.mcp_client import call_browser_tool


@tool
async def browser_read(action: str):
    """
    Inspect and extract information from the current webpage.
    Available actions:
    - snapshot (prefer for page understanding)
    - screenshot (visual only)
    - console (for debugging)
    - network (API inspection)
    """
    action_map = {
        "snapshot": "browser_snapshot",
        "screenshot": "browser_take_screenshot",
        "console": "browser_console_messages",
        "network": "browser_network_requests",
    }

    tool_name = action_map.get(action)
    if not tool_name:
        return "Invalid browser read action. Use snapshot, screenshot, console, or network."

    try:
        result = await call_browser_tool(tool_name, {})
        text = result.content[0].text if result.content else "No content returned"

        if action == "screenshot":
            return "Screenshot captured successfully."

        # Avoid aggressive truncation of the snapshot, limit to 4000 characters to fit LLM window
        return text[:4000] + ("\n... [truncated]" if len(text) > 4000 else "")
    except Exception as e:
        return f"Error executing {tool_name}: {str(e)}"
