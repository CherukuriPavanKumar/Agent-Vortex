from langchain.tools import tool
from core_setup.mcp_client import call_browser_tool


@tool
async def browser_interaction(
    action: str,
    target: str | None = None,
    text: str | None = None,
    key: str | None = None,
):
    """
    Interact with webpage elements.
    Requires element unique 'target' (ref) from snapshots.

    Actions:
    - "click": click an element
    - "hover": hover over an element
    - "type": type text into an element (requires 'text')
    - "press_key": press a key like "Enter" on an element (requires 'key')
    """
    try:
        if action == "click":
            res = await call_browser_tool("browser_click", {"target": target})
        elif action == "hover":
            res = await call_browser_tool("browser_hover", {"target": target})
        elif action == "type" and text:
            res = await call_browser_tool(
                "browser_type", {"target": target, "text": text}
            )
        elif action == "press_key" and key:
            res = await call_browser_tool("browser_press_key", {"key": key})
        else:
            return "Invalid action or missing parameters (e.g. text for 'type')."

        return (
            res.content[0].text
            if res.content
            else f"Action {action} completed on {target}."
        )
    except Exception as e:
        return f"Interaction error: {str(e)}"
