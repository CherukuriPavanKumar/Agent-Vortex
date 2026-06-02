import asyncio
import getpass
from uuid import UUID

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
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

from memory.title_generator import (
    generate_title,
)

from memory.ltm.service import (
    extract_and_store_memories,
)

load_dotenv()


# ==========================================================
# UI Helpers
# ==========================================================


def print_banner() -> None:
    print(
        "\n"
        "=================================================\n"
        "                 Agent Vortex V2\n"
        "=================================================\n"
    )


def print_separator() -> None:
    print(
        "\n"
        "-------------------------------------------------\n"
    )


def print_assistant_response(content) -> None:
    """
    Gemini sometimes returns:
    - str
    - list
    - multimodal blocks

    Normalize output.
    """

    print("\nAssistant:\n")

    if isinstance(content, str):
        print(content)
        return

    if isinstance(content, list):
        for item in content:

            if isinstance(item, str):
                print(item)

            elif isinstance(item, dict):
                if "text" in item:
                    print(item["text"])

            else:
                print(str(item))

        return

    print(str(content))


# ==========================================================
# Conversation Selection
# ==========================================================


def select_conversation() -> tuple[str, bool]:
    """
    Returns:
        (conversation_id, is_new)
    """

    conversations = list_conversations()

    print("\nConversations:\n")

    if conversations:

        for idx, convo in enumerate(
            conversations,
            start=1,
        ):
            convo_id, title, created_at = convo

            title = (
                title
                if title
                else "Untitled Conversation"
            )

            print(
                f"{idx}. {title}"
            )

        print(
            "\nN. New Conversation"
        )

        choice = (
            input("\nSelect: ")
            .strip()
            .lower()
        )

        if choice == "n":

            conversation_id = create_conversation()

            return conversation_id, True

        try:

            selected = conversations[
                int(choice) - 1
            ]

            return str(selected[0]), False

        except Exception:

            print(
                "\nInvalid choice. Creating new conversation."
            )

    conversation_id = create_conversation()

    return conversation_id, True


# ==========================================================
# Approval Handling
# ==========================================================


async def handle_interrupts(
    graph,
    result,
    config,
):
    """
    Handle HITL approval workflow.
    """

    while "__interrupt__" in result:

        interrupt = (
            result["__interrupt__"][0]
            .value
        )

        print_separator()

        print(
            "Approval Required\n"
        )

        print(
            f"Risk Level: "
            f"{interrupt.get('risk_level')}"
        )

        print(
            "\nPlanned Actions:"
        )

        for idx, step in enumerate(
            interrupt.get(
                "plan",
                [],
            ),
            start=1,
        ):
            print(
                f"{idx}. {step}"
            )

        print(
            "\nTools:"
        )

        for tool in interrupt.get(
            "planned_tools",
            [],
        ):
            print(
                f"• {tool}"
            )

        approved = (
            input(
                "\nApprove? (y/n): "
            )
            .strip()
            .lower()
        )

        result = await graph.ainvoke(
            Command(
                resume=approved == "y"
            ),
            config=config,
        )

    return result


# ==========================================================
# Chat Loop
# ==========================================================


async def run_chat_loop(
    graph,
    conversation_id: str,
    tools,
    is_new_conversation: bool,
):
    """
    Main conversation runtime.
    """

    config = {
        "configurable": {
            "thread_id": conversation_id,
            "user_id": getpass.getuser(),
            "tools": tools,
        }
    }

    title_generated = False

    while True:

        try:

            user_input = (
                input("\nYou: ")
                .strip()
            )

            if not user_input:
                continue

            if user_input.lower() in {
                "exit",
                "quit",
            }:
                break

            result = await graph.ainvoke(
                {
                    "messages": [
                        HumanMessage(
                            content=user_input
                        )
                    ]
                },
                config=config,
            )

            result = await handle_interrupts(
                graph,
                result,
                config,
            )

            if result.get("error"):

                print(
                    f"\n[Error]\n"
                    f"{result['error']}"
                )

                continue

            messages = result.get(
                "messages",
                []
            )

            if messages:

                print_assistant_response(
                    messages[-1].content
                )

            # --------------------------------------
            # Generate title once
            # --------------------------------------

            if (
                is_new_conversation
                and not title_generated
            ):

                try:
                    
                    title = await generate_title(user_input)

                    update_title(
                        conversation_id,
                        title,
                    )   

                    title_generated = True

                except Exception as e:

                    print(
                        f"\n[Title Generation Failed] {e}"
                    )

        except KeyboardInterrupt:

            print(
                "\n\nStopping conversation..."
            )

            break

        except Exception as e:

            print(
                f"\nRuntime Error: {e}"
            )


# ==========================================================
# Startup
# ==========================================================


async def startup():
    """
    Initialize Agent Vortex.
    """

    print_banner()

    print(
        "[1/6] Bootstrapping database..."
    )

    await bootstrap_database()

    print(
        "[2/6] Checking LLM..."
    )

    llm_status = await health_check()

    print(
        f"LLM Response: {llm_status}"
    )

    print(
        "[3/6] Connecting Browser MCP..."
    )
    
    await initialize_browser_mcp()

    print(
        "[4/6] Loading tools..."
    )

    tools = load_tools()

    print(
        "[5/6] Connecting checkpointer..."
    )

    checkpointer_ctx = (
        get_checkpointer()
    )

    checkpointer = (
        await checkpointer_ctx.__aenter__()
    )

    print(
        "[6/6] Building graph..."
    )

    graph = build_graph(
        tools=tools,
        checkpointer=checkpointer,
    )

    print(
        "\nAgent Vortex Ready.\n"
    )

    return (
        graph,
        tools,
        checkpointer_ctx,
    )


# ==========================================================
# Shutdown
# ==========================================================


async def shutdown(
    conversation_id: str,
    checkpointer_ctx,
    graph,
):
    """
    Extract memories and close resources.
    """

    try:

        print(
            "\nExtracting memories..."
        )

        config = {
            "configurable": {
                "thread_id": conversation_id,
            }
        }
        
        state = await graph.aget_state(config)
        messages = state.values.get("messages", [])

        await extract_and_store_memories(
            messages,
            user_id=getpass.getuser()
        )

    except Exception as e:

        print(
            f"\nMemory extraction failed: {e}"
        )

    try:

        await checkpointer_ctx.__aexit__(
            None,
            None,
            None,
        )

    except Exception:
        pass

    try:
        print("\nShutting down Browser MCP...")
        await shutdown_browser_mcp()
    except Exception as e:
        print(f"\nBrowser MCP shutdown failed: {e}")


# ==========================================================
# Main
# ==========================================================


async def main():

    (
        graph,
        tools,
        checkpointer_ctx,
    ) = await startup()

    conversation_id = None

    try:

        conversation_id, is_new = (
            select_conversation()
        )

        await run_chat_loop(
            graph=graph,
            conversation_id=conversation_id,
            tools=tools,
            is_new_conversation=is_new,
        )

    finally:

        if conversation_id:

            await shutdown(
                conversation_id,
                checkpointer_ctx,
                graph,
            )

if __name__ == "__main__":
    asyncio.run(main())