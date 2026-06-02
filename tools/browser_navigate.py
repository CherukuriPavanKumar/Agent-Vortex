from langchain.tools import tool
from core_setup.mcp_client import call_browser_tool


@tool
async def browser_navigate(url: str | None = None, direction: str | None = None):
    """
    Navigate browser pages.
    - Use url to open a website
    - Use direction='back' to go back
    """
    try:
        if url:
            result = await call_browser_tool("browser_navigate", {"url": url})
        elif direction == "back":
            result = await call_browser_tool("browser_navigate_back", {})
        else:
            return "Invalid navigation request. Provide url or direction='back'."

        text = result.content[0].text if result.content else "Navigated successfully."
        # Return sensible substring in case text is very large
        return text[:1000]
    except Exception as e:
        return f"Navigation error: {str(e)}"
