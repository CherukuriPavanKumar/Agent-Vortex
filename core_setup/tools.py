from typing import Any

from core_setup.google_auth_check import (
    is_google_configured,
)

# ----------------------------------------------------------
# Core Tools
# ----------------------------------------------------------

from tools.terminal_tool import terminal_tool

from tools.generate_pdf import generate_pdf
from tools.generate_excel import generate_excel

# ----------------------------------------------------------
# Browser Tools
# ----------------------------------------------------------

from tools.browser_navigate import browser_navigate
from tools.browser_read import browser_read
from tools.browser_interaction import browser_interaction
from tools.browser_tabs import browser_tabs

# ----------------------------------------------------------
# Gmail Tools
# ----------------------------------------------------------

from tools.gmail_read import gmail_read
from tools.gmail_send import gmail_send

# ----------------------------------------------------------
# Calendar Tools
# ----------------------------------------------------------

from tools.calendar_read import calendar_read
from tools.calendar_write import calendar_write


# ==========================================================
# Tool Groups
# ==========================================================

BASE_TOOLS = [
    terminal_tool,
    generate_pdf,
    generate_excel,
    browser_navigate,
    browser_read,
    browser_interaction,
    browser_tabs,
]

GOOGLE_TOOLS = [
    gmail_read,
    gmail_send,
    calendar_read,
    calendar_write,
]


# ==========================================================
# Tool Metadata
# ==========================================================

TOOL_DESCRIPTIONS = {
    "terminal_tool": (
        "Execute Linux shell commands for filesystem operations, local code execution, "
        "package management (pip/apt), git operations, and system inspection. "
        "NEVER use this for web browsing, URLs, or fetching online content. "
        "Do NOT use curl, wget, or lynx for websites — use browser_navigate instead."
    ),
    "browser_navigate": (
        "Open and navigate websites using a real Chromium browser. "
        "USE THIS for ALL URL/website tasks: opening http:// or https:// links, "
        "visiting news sites, documentation, web apps, search engines, "
        "any online page. This is the ONLY correct tool for web navigation. "
        "NEVER use terminal_tool or curl to open URLs."
    ),
    "browser_read": (
        "Read and extract content from the currently open webpage. "
        "USE THIS after browser_navigate to get text, titles, headings, links, "
        "news headlines, article content, search results, and any page data. "
        "Default action is 'snapshot' which returns the full page text. "
        "NEVER use terminal_tool to read webpage content."
    ),
    "browser_interaction": (
        "Click, type, hover, and interact with elements on the current webpage. "
        "Use for clicking buttons/links, filling forms, submitting search queries, "
        "pressing keyboard keys on web elements. Requires element ref from browser_read snapshot. "
        "NEVER use terminal_tool for web interactions."
    ),
    "browser_tabs": (
        "Manage browser tabs: list, create, switch between, or close tabs. "
        "Use when working with multiple websites simultaneously. "
        "NEVER use terminal_tool for browser tab management."
    ),
    "whatsapp_send_message": (
        "Send WhatsApp messages to contacts via the WhatsApp MCP server."
    ),
    "gmail_read": (
        "Read and search emails from Gmail inbox. Use for email retrieval tasks."
    ),
    "gmail_send": (
        "Send emails through Gmail. Use for email composition and delivery tasks."
    ),
    "calendar_read": (
        "Read and list events from Google Calendar. Use for schedule lookup tasks."
    ),
    "calendar_write": (
        "Create, update, and manage Google Calendar events. Use for scheduling tasks."
    ),
    "generate_pdf": (
        "Generate PDF documents from structured content or HTML. "
        "Use when the user requests a PDF file output."
    ),
    "generate_excel": (
        "Generate Excel spreadsheets (.xlsx) from structured tabular data. "
        "Use when the user requests an Excel or spreadsheet file output."
    ),
}


# ==========================================================
# WhatsApp Helpers
# ==========================================================

def load_whatsapp_tools() -> list[Any]:

    try:

        from tools.whatsapp_tool import (
            whatsapp_send_message,
        )

        print(
            "[WhatsApp] Tool loaded."
        )

        return [
            whatsapp_send_message
        ]

    except Exception as e:

        print(
            f"[WhatsApp] Disabled ({e})."
        )

        return []

# ==========================================================
# Utility Functions
# ==========================================================

def get_tool_names(
    tools: list[Any],
) -> list[str]:
    """
    Return all tool names.
    """

    return [
        tool.name
        for tool in tools
    ]


def get_tool_map(
    tools: list[Any],
) -> dict[str, Any]:
    """
    Build a name -> tool lookup map.
    """

    return {
        tool.name: tool
        for tool in tools
    }


def build_tool_context(
    tools: list[Any],
) -> str:
    """
    Build planner-friendly tool descriptions.
    """

    lines = []

    for tool in tools:
        description = TOOL_DESCRIPTIONS.get(
            tool.name,
            getattr(
                tool,
                "description",
                "No description available.",
            ),
        )

        lines.append(
            f"- {tool.name}: {description}"
        )

    return "\n".join(lines)


def validate_tools(
    tools: list[Any],
) -> None:
    """
    Ensure there are no duplicate tool names.
    """

    names = get_tool_names(tools)

    duplicates = {
        name
        for name in names
        if names.count(name) > 1
    }

    if duplicates:
        raise ValueError(
            f"Duplicate tool names detected: {duplicates}"
        )


def print_loaded_tools(
    tools: list[Any],
) -> None:
    """
    Print all loaded tools.
    """

    print("\nLoaded Tools:")

    for tool in tools:
        print(
            f"  • {tool.name}"
        )


# ==========================================================
# Main Loader
# ==========================================================

def load_tools() -> list[Any]:
    """
    Build the final tool registry.

    Tool availability:

    - Core tools: always enabled
    - Browser tools: always enabled
    - WhatsApp tools: enabled only if MCP is healthy
    - Google tools: enabled only if OAuth is configured
    """

    tools = list(BASE_TOOLS)

    print(
        f"[Core] Loaded {len(BASE_TOOLS)} core tools."
    )

    # ------------------------------------------------------
    # WhatsApp
    # ------------------------------------------------------

    whatsapp_tools = load_whatsapp_tools()

    if whatsapp_tools:
        tools.extend(
            whatsapp_tools
        )

    # ------------------------------------------------------
    # Google
    # ------------------------------------------------------

    if is_google_configured():

        tools.extend(
            GOOGLE_TOOLS
        )

        print(
            f"[Google] Loaded {len(GOOGLE_TOOLS)} tools."
        )

    else:

        print(
            "[Google] Disabled."
        )

    # ------------------------------------------------------
    # Validation
    # ------------------------------------------------------

    validate_tools(tools)

    # ------------------------------------------------------
    # Startup Summary
    # ------------------------------------------------------

    print_loaded_tools(tools)

    print(
        f"\n[Tools] Total loaded: {len(tools)}"
    )

    return tools