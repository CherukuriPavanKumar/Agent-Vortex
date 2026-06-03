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
    Interact with elements on the currently open webpage in the browser.

    USE THIS TOOL to:
    - Click buttons, links, checkboxes, dropdowns on a webpage
    - Type text into search boxes, forms, input fields on a website
    - Hover over elements on a webpage
    - Press keyboard keys (Enter, Tab, Escape) on a webpage element
    - Submit forms on websites

    ALWAYS use browser_navigate to open the page and browser_read(action="snapshot")
    to get element references (target) BEFORE interacting.
    NEVER use terminal_tool for clicking or typing on webpages.

    Actions:
    - "click": click an element (requires 'target' ref from snapshot)
    - "hover": hover over an element (requires 'target' ref)
    - "type": type text into an input field (requires 'target' and 'text')
    - "press_key": press a keyboard key (requires 'key', e.g. "Enter", "Tab")
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
