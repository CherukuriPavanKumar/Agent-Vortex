from langchain.tools import tool
from core_setup.mcp_client import call_browser_tool


@tool
async def browser_navigate(url: str | None = None, direction: str | None = None):
    """
    Open and navigate websites using a real Chromium browser (Playwright MCP).

    USE THIS TOOL for ALL of the following:
    - Opening any URL or web address (http://, https://)
    - Visiting websites, webpages, web apps, online tools
    - Web browsing, navigation, going back/forward
    - Accessing news sites, documentation, search engines, social platforms
    - Any task that involves a URL or a website

    NEVER use terminal_tool, curl, wget, lynx, or any shell command to access URLs.
    This tool is the ONLY correct way to open websites.

    Parameters:
    - url: Full URL to navigate to (e.g. "https://news.ycombinator.com")
    - direction: Use 'back' to navigate back to the previous page

    Examples:
    - browser_navigate(url="https://news.ycombinator.com")
    - browser_navigate(url="https://google.com")
    - browser_navigate(direction="back")
    """
    try:
        if url:
            result = await call_browser_tool("browser_navigate", {"url": url})
        elif direction == "back":
            result = await call_browser_tool("browser_navigate_back", {})
        else:
            return "Invalid navigation request. Provide url or direction='back'."

        text = result.content[0].text if result.content else "Navigated successfully."
        return text[:1000]
    except Exception as e:
        return f"Navigation error: {str(e)}"
