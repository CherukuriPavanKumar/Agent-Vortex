import asyncio
import getpass
import json
import os
import sys
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv

from langchain_core.messages import HumanMessage, AIMessage
from langgraph.types import Command

from core_setup.bootstrap import bootstrap_database
from core_setup.checkpointer import get_checkpointer
from core_setup.llm import health_check
from core_setup.tools import load_tools
from core_setup.mcp_client import initialize_browser_mcp, shutdown_browser_mcp
from nodes.builder import build_graph

from memory.conversations import (
    create_conversation,
    list_conversations,
    update_title,
)
from memory.title_generator import generate_title
from memory.ltm.service import extract_and_store_memories

load_dotenv()


# ==========================================================
# Global State
# ==========================================================

app_state: dict[str, Any] = {}

AGENT_PASSWORD = os.getenv("AGENT_PASSWORD", "")


# ==========================================================
# Lifespan
# ==========================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle for the FastAPI app."""

    print("[API] Bootstrapping database...")
    await bootstrap_database()

    print("[API] Checking LLM...")
    llm_status = await health_check()
    print(f"  LLM Response: {llm_status}")

    print("[API] Connecting Browser MCP...")
    await initialize_browser_mcp()

    print("[API] Loading tools...")
    tools = load_tools()
    app_state["tools"] = tools

    print("[API] Connecting checkpointer...")
    checkpointer_ctx = get_checkpointer()
    checkpointer = await checkpointer_ctx.__aenter__()
    app_state["checkpointer_ctx"] = checkpointer_ctx

    print("[API] Building graph...")
    graph = build_graph(tools=tools, checkpointer=checkpointer)
    app_state["graph"] = graph

    if AGENT_PASSWORD:
        print(f"[API] Auth enabled (password set)")
    else:
        print("[API] Auth disabled (no AGENT_PASSWORD in .env)")

    print("[API] Ready.\n")
    yield

    # Shutdown — extract memories for all active threads
    print("[API] Shutting down...")

    try:
        await checkpointer_ctx.__aexit__(None, None, None)
    except Exception as e:
        print(f"  Checkpointer exit error: {e}")

    try:
        await shutdown_browser_mcp()
    except Exception as e:
        print(f"  Browser MCP shutdown error: {e}")


# ==========================================================
# App
# ==========================================================

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==========================================================
# Authentication
# ==========================================================

async def verify_auth(request: Request):
    """
    Simple token-based auth.
    Frontend sends 'Authorization: Bearer <password>' header.
    Skipped if AGENT_PASSWORD is not set.
    """
    if not AGENT_PASSWORD:
        return

    # Allow the auth endpoint itself
    if request.url.path == "/api/auth":
        return

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")

    token = auth_header[7:]
    if token != AGENT_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid password")


# ==========================================================
# Schemas
# ==========================================================

class ChatRequest(BaseModel):
    message: str


class ApproveRequest(BaseModel):
    approved: bool


class AuthRequest(BaseModel):
    password: str


# ==========================================================
# Helpers
# ==========================================================

def _build_config(conversation_id: str) -> dict:
    return {
        "configurable": {
            "thread_id": conversation_id,
            "user_id": getpass.getuser(),
            "tools": app_state.get("tools"),
        }
    }


def _normalize_content(content) -> str:
    """Normalize LLM response content to a plain string."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and "text" in item:
                parts.append(item["text"])
            else:
                parts.append(str(item))
        return "\n".join(parts)
    return str(content)


def _sse_event(data: dict) -> str:
    """Format a single SSE event."""
    return f"data: {json.dumps(data)}\n\n"


# ==========================================================
# Endpoints — Auth
# ==========================================================

@app.post("/api/auth")
async def authenticate(req: AuthRequest):
    """Verify password and return success if correct."""
    if not AGENT_PASSWORD:
        return {"authenticated": True}

    if req.password == AGENT_PASSWORD:
        return {"authenticated": True, "token": AGENT_PASSWORD}

    raise HTTPException(status_code=401, detail="Wrong password")


# ==========================================================
# Endpoints — Conversations
# ==========================================================

@app.get("/api/conversations", dependencies=[Depends(verify_auth)])
async def get_conversations():
    convos = list_conversations()
    return [
        {
            "id": str(c[0]),
            "title": c[1] or "Untitled",
            "created_at": c[2],
        }
        for c in convos
    ]


@app.post("/api/conversations", dependencies=[Depends(verify_auth)])
async def create_new_conversation():
    convo_id = create_conversation()
    return {"id": convo_id}


# ==========================================================
# Endpoints — Chat History
# ==========================================================

@app.get("/api/chat/{conversation_id}", dependencies=[Depends(verify_auth)])
async def get_chat_history(conversation_id: str):
    graph = app_state.get("graph")
    if not graph:
        raise HTTPException(status_code=500, detail="Graph not initialized")

    config = {"configurable": {"thread_id": conversation_id}}
    state = await graph.aget_state(config)

    messages = []
    for msg in state.values.get("messages", []):
        messages.append({
            "role": "user" if isinstance(msg, HumanMessage) else "assistant",
            "content": _normalize_content(msg.content),
        })

    # Check for pending interrupt
    interrupt = None
    if hasattr(state, "tasks") and state.tasks:
        for task in state.tasks:
            if hasattr(task, "interrupts") and task.interrupts:
                iv = task.interrupts[0].value
                interrupt = {
                    "risk_level": iv.get("risk_level") or iv.get("risk", "low"),
                    "plan": iv.get("plan", []),
                    "planned_tools": iv.get("planned_tools", iv.get("tools", [])),
                }
                break

    return {"messages": messages, "interrupt": interrupt}


# ==========================================================
# Endpoints — Streaming Chat
# ==========================================================

@app.post("/api/chat/{conversation_id}/stream", dependencies=[Depends(verify_auth)])
async def chat_stream(conversation_id: str, req: ChatRequest):
    """
    SSE streaming endpoint.

    Events sent:
      - {type: "token", content: "..."}    — incremental LLM text
      - {type: "interrupt", ...}           — HITL approval required
      - {type: "done", content: "..."}     — final complete message
      - {type: "error", content: "..."}    — error
    """
    graph = app_state.get("graph")
    if not graph:
        raise HTTPException(status_code=500, detail="Graph not initialized")

    config = _build_config(conversation_id)

    async def event_generator():
        accumulated = ""

        try:
            async for event in graph.astream_events(
                {"messages": [HumanMessage(content=req.message)]},
                config=config,
                version="v2",
            ):
                kind = event["event"]

                # Stream individual tokens from the LLM
                if kind == "on_chat_model_stream":
                    chunk = event["data"].get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        token = chunk.content
                        if isinstance(token, str) and token:
                            accumulated += token
                            yield _sse_event({"type": "token", "content": token})

        except Exception as e:
            yield _sse_event({"type": "error", "content": str(e)})
            return

        # After stream completes, check for interrupt
        try:
            state = await graph.aget_state(config)

            has_interrupt = False
            if hasattr(state, "tasks") and state.tasks:
                for task in state.tasks:
                    if hasattr(task, "interrupts") and task.interrupts:
                        iv = task.interrupts[0].value
                        yield _sse_event({
                            "type": "interrupt",
                            "risk_level": iv.get("risk_level") or iv.get("risk", "low"),
                            "plan": iv.get("plan", []),
                            "planned_tools": iv.get("planned_tools", iv.get("tools", [])),
                        })
                        has_interrupt = True
                        break

            if not has_interrupt:
                # Get the final full message from state
                msgs = state.values.get("messages", [])
                if msgs:
                    final = _normalize_content(msgs[-1].content)
                    yield _sse_event({"type": "done", "content": final})
                else:
                    yield _sse_event({"type": "done", "content": accumulated})

        except Exception as e:
            yield _sse_event({"type": "done", "content": accumulated or str(e)})

        # Generate title for first message and send as SSE event
        try:
            from memory.conversations import get_conversation
            convo = get_conversation(conversation_id)
            if convo and not convo[1]:  # Title is None initially
                title = await generate_title(req.message)
                update_title(conversation_id, title)
                yield _sse_event({"type": "title", "content": title})
        except Exception as e:
            print(f"[Title Generation Error]: {e}")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ==========================================================
# Endpoints — Non-streaming Chat (fallback)
# ==========================================================

@app.post("/api/chat/{conversation_id}", dependencies=[Depends(verify_auth)])
async def chat(conversation_id: str, req: ChatRequest):
    graph = app_state.get("graph")
    if not graph:
        raise HTTPException(status_code=500, detail="Graph not initialized")

    config = _build_config(conversation_id)

    try:
        result = await graph.ainvoke(
            {"messages": [HumanMessage(content=req.message)]},
            config=config,
        )

        # Generate title for first message
        try:
            state = await graph.aget_state(config)
            msg_count = len(state.values.get("messages", []))
            if msg_count <= 2:
                title = await generate_title(req.message)
                update_title(conversation_id, title)
        except Exception:
            pass

        return _format_result(result)

    except Exception as e:
        print(f"Chat error: {e}", file=sys.stderr)
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================================
# Endpoints — Approval
# ==========================================================

@app.post("/api/approve/{conversation_id}", dependencies=[Depends(verify_auth)])
async def approve(conversation_id: str, req: ApproveRequest):
    graph = app_state.get("graph")
    if not graph:
        raise HTTPException(status_code=500, detail="Graph not initialized")

    config = _build_config(conversation_id)

    try:
        result = await graph.ainvoke(
            Command(resume=req.approved),
            config=config,
        )
        return _format_result(result)
    except Exception as e:
        print(f"Approve error: {e}", file=sys.stderr)
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================================
# Endpoints — Memory Extraction
# ==========================================================

@app.post("/api/conversations/{conversation_id}/memories", dependencies=[Depends(verify_auth)])
async def extract_memories(conversation_id: str):
    """
    Manually trigger long-term memory extraction for a conversation.
    Called by the frontend when switching away from a conversation.
    """
    graph = app_state.get("graph")
    if not graph:
        raise HTTPException(status_code=500, detail="Graph not initialized")

    config = {"configurable": {"thread_id": conversation_id}}

    try:
        state = await graph.aget_state(config)
        messages = state.values.get("messages", [])

        if not messages:
            return {"extracted": False, "reason": "No messages in conversation"}

        await extract_and_store_memories(
            messages,
            user_id=getpass.getuser(),
        )

        return {"extracted": True, "message_count": len(messages)}

    except Exception as e:
        print(f"Memory extraction error: {e}", file=sys.stderr)
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================================
# Result Formatter
# ==========================================================

def _format_result(result: dict) -> dict:
    if "__interrupt__" in result:
        interrupt = result["__interrupt__"][0].value
        return {
            "status": "interrupt",
            "risk_level": interrupt.get("risk_level") or interrupt.get("risk", "low"),
            "plan": interrupt.get("plan", []),
            "planned_tools": interrupt.get("planned_tools", interrupt.get("tools", [])),
        }

    if result.get("error"):
        return {"status": "error", "error": result["error"]}

    messages = result.get("messages", [])
    if not messages:
        return {"status": "success", "message": "No response."}

    return {
        "status": "success",
        "message": _normalize_content(messages[-1].content),
    }
