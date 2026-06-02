import os
import asyncio
import httpx
from fastmcp import Client


class _BearerAuth(httpx.Auth):
    """Minimal httpx.Auth that injects an Authorization: Bearer header.

    httpx ships no BearerTokenAuth class — only BasicAuth and a callable.
    Passing a plain string to Client(auth=...) is silently ignored, so every
    request would go out without an Authorization header and the Go sidecar
    returns 401 Unauthorized. This class implements auth_flow() correctly.
    """

    def __init__(self, token: str):
        self._header = f"Bearer {token}"

    def auth_flow(self, request: httpx.Request):
        request.headers["Authorization"] = self._header
        yield request

# ── Playwright MCP (stdio) ────────────────────────────────────────────────────
client = Client(
    {
        "mcpServers": {
            "playwright": {
                "command": "npx",
                # --headless: required for Docker / servers with no display.
                # Without this flag Chromium tries to open a visible window and
                # immediately fails in headless environments.
                "args": ["-y", "@playwright/mcp@latest", "--headless"],
            }
        }
    }
)

async def initialize_browser_mcp():
    print("[Browser MCP] Connecting...")
    await client.__aenter__()
    try:
        tools = await client.list_tools()
        print(f"[Browser MCP] Connected.")
        print(f"[Browser MCP] {len(tools)} tools available.")
    except Exception as e:
        print(f"[Browser MCP] Error connecting: {e}")

async def shutdown_browser_mcp():
    await client.__aexit__(None, None, None)

async def call_browser_tool(tool_name: str, arguments: dict):
    return await client.call_tool(tool_name, arguments)

# ── WhatsApp MCP (HTTP sidecar) ────────────────────────────────────────────────
_WHATSAPP_MCP_URL = os.environ.get("WHATSAPP_MCP_URL", "http://127.0.0.1:8765/mcp")
_WHATSAPP_MCP_TOKEN = os.environ.get("WHATSAPP_MCP_TOKEN", "")

# Tracks whether WhatsApp MCP was successfully connected at boot.
# main.py reads this to decide whether to include WhatsApp tools.
whatsapp_available: bool = False


def make_whatsapp_client() -> Client:
    """
    Create a fresh WhatsApp MCP Client for each tool invocation.

    Why a factory instead of a singleton?
    - The singleton pattern caused a lifecycle bug: probe_whatsapp() entered and
      exited the client (async with), leaving it in a closed state. Any subsequent
      `async with whatsapp_client:` in the tool would silently reconnect without
      properly re-applying auth headers.
    - A fresh Client per call is cheap (HTTP, not a persistent socket) and
      guarantees a clean session with correct auth on every tool invocation.

    Why httpx.BearerTokenAuth instead of auth=<string>?
    - httpx.Client.auth expects an httpx.Auth subclass, a (user, password) tuple,
      or a callable. Passing a plain string is silently ignored, meaning every
      request goes out without an Authorization header and the Go sidecar returns
      401 Unauthorized.
    """
    if _WHATSAPP_MCP_TOKEN:
        auth = _BearerAuth(_WHATSAPP_MCP_TOKEN)
    else:
        auth = None
    return Client(_WHATSAPP_MCP_URL, auth=auth)


async def probe_whatsapp(timeout: float = 5.0) -> bool:
    """
    Try to connect to the WhatsApp MCP server and list its tools.
    Returns True if healthy, False if unreachable or timed out.
    Uses make_whatsapp_client() so probe uses the same auth path as tool calls.
    """
    global whatsapp_available
    try:
        async with asyncio.timeout(timeout):
            wa_client = make_whatsapp_client()
            async with wa_client:
                tools = await wa_client.list_tools()
                whatsapp_available = len(tools) > 0
                return whatsapp_available
    except Exception as e:
        print(f"[WhatsApp MCP] Not available: {e}")
        whatsapp_available = False
        return False
