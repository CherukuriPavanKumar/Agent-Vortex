from langchain.tools import tool
from langchain_community.tools import ShellTool

shell = ShellTool()


@tool
async def terminal_tool(command: str):
    """
    Execute Linux shell commands for:
    - filesystem operations
    - project setup
    - package management
    - system inspection
    - git operations

    Rules:
    Do NOT use this tool for:
    - web scraping
    - webpage extraction
    - webpage understanding
    - HTML parsing
    - browser automation

    Use browser tools for all web-related tasks.

    - Prefer single combined commands.
    - Avoid unnecessary command repetition.
    - Avoid Destructive Operations like deleting etc
    - Use shell chaining when appropriate.
    - Do not use terminal commands for reasoning.
    - Use terminal only for execution and filesystem operations.
    """

    return await shell.ainvoke({"commands": command})
