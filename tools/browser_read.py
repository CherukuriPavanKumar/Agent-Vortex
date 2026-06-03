from langchain.tools import tool
from core_setup.mcp_client import call_browser_tool


@tool
async def browser_read(action: str = "snapshot"):
    """
    Read, extract, and understand content from the currently open webpage in the browser.

    USE THIS TOOL to:
    - Read text, titles, links, headings from a webpage after navigating to it
    - Extract article content, news headlines, search results, listings
    - Understand the structure and content of any open webpage
    - Get a full page snapshot (default and recommended)
    - Take a screenshot for visual inspection
    - Read browser console logs or network requests

    ALWAYS call browser_navigate first to open a page, then call browser_read to get its content.
    NEVER use terminal_tool, curl, or wget to read webpage content.

    Parameters:
    - action: What to read from the page. Options:
        * "snapshot" (DEFAULT - use this to read all page text and structure)
        * "screenshot" (visual only, returns confirmation)
        * "console" (browser JavaScript console logs)
        * "network" (HTTP requests made by the page)

    Examples:
    - browser_read()  # reads page content (snapshot by default)
    - browser_read(action="snapshot")  # same as above
    - browser_read(action="screenshot")  # take a screenshot
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
