from langchain.tools import tool
from core_setup.mcp_client import make_whatsapp_client

import asyncio
import json
import logging
import re

logger = logging.getLogger(__name__)

PHONE_REGEX = re.compile(r"^\+?\d{10,15}$")


def is_phone_number(value: str) -> bool:
    """
    Detect whether user provided
    a phone number directly.
    """
    cleaned = value.replace(" ", "").replace("-", "")
    return bool(PHONE_REGEX.match(cleaned))


def normalize_phone_number(number: str) -> str:
    """
    Convert:

        +91 9542421642
        91-9542421642
        9542421642

    into:

        919542421642
    """

    digits = "".join(
        c for c in number
        if c.isdigit()
    )

    if len(digits) == 10:
        digits = f"91{digits}"

    return digits


@tool
async def whatsapp_send_message(
    contact_name: str,
    message: str,
) -> str:
    """
    Send a WhatsApp message.

    Supports:

    - Contact names
    - Direct phone numbers

    Phone numbers are the most reliable option.
    """

    logger.info(
        "WhatsApp send requested"
    )

    try:

        wa_client = make_whatsapp_client()

        async with wa_client:

            # --------------------------------------------------
            # Direct Phone Number Path
            # --------------------------------------------------

            if is_phone_number(
                contact_name
            ):

                recipient = normalize_phone_number(
                    contact_name
                )

                logger.info(
                    f"Using direct phone number: {recipient}"
                )

            else:

                # --------------------------------------------------
                # Contact Lookup Path
                # --------------------------------------------------

                logger.info(
                    f"Searching contact: {contact_name}"
                )

                contacts_result = (
                    await asyncio.wait_for(
                        wa_client.call_tool(
                            "search_contacts",
                            {
                                "query": contact_name
                            },
                        ),
                        timeout=15,
                    )
                )

                if not contacts_result.content:

                    return (
                        f"Could not find WhatsApp contact "
                        f"'{contact_name}'.\n\n"
                        "The WhatsApp MCP server only knows "
                        "contacts that exist in its cache.\n\n"
                        "Please provide the phone number "
                        "instead."
                    )

                raw_text = (
                    contacts_result.content[0].text
                )

                try:
                    contacts = json.loads(
                        raw_text
                    )
                except json.JSONDecodeError:

                    logger.error(
                        f"Invalid contact response: {raw_text}"
                    )

                    return (
                        "WhatsApp contact lookup "
                        "returned an invalid response."
                    )

                if not contacts:

                    return (
                        f"Contact '{contact_name}' "
                        "was not found.\n\n"
                        "Please provide the phone number."
                    )

                # ------------------------------------------
                # Multiple Matches
                # ------------------------------------------

                if (
                    isinstance(contacts, list)
                    and len(contacts) > 1
                ):

                    matches = []

                    for c in contacts[:5]:

                        matches.append(
                            f"- {c.get('name')} "
                            f"({c.get('phone_number')})"
                        )

                    return (
                        f"Multiple contacts matched "
                        f"'{contact_name}'.\n\n"
                        + "\n".join(matches)
                        + "\n\n"
                        + "Please be more specific."
                    )

                contact = (
                    contacts[0]
                    if isinstance(
                        contacts,
                        list,
                    )
                    else contacts
                )

                recipient = (
                    contact.get(
                        "phone_number"
                    )
                    or contact.get(
                        "jid"
                    )
                )

                if not recipient:

                    return (
                        "Contact found but no "
                        "phone number was available."
                    )

            # --------------------------------------------------
            # Send Message
            # --------------------------------------------------

            send_result = (
                await asyncio.wait_for(
                    wa_client.call_tool(
                        "send_message",
                        {
                            "recipient": recipient,
                            "message": message,
                        },
                    ),
                    timeout=15,
                )
            )

            if (
                hasattr(
                    send_result,
                    "content",
                )
                and send_result.content
            ):

                text_parts = [
                    item.text
                    for item in send_result.content
                    if hasattr(
                        item,
                        "text",
                    )
                ]

                if text_parts:

                    return "\n".join(
                        text_parts
                    )

            return (
                f"Message sent successfully "
                f"to {recipient}."
            )

    except asyncio.TimeoutError:

        logger.error(
            "WhatsApp MCP timeout"
        )

        return (
            "WhatsApp MCP server timed out."
        )

    except Exception as e:

        logger.exception(
            "WhatsApp send failed"
        )

        return (
            f"WhatsApp error: {str(e)}"
        )


@tool
async def whatsapp_list_chats(
    query: str | None = None,
    limit: int = 15,
) -> str:
    """
    List cached WhatsApp conversations (both 1:1 direct chats and group chats).

    USE THIS TOOL to:
    - View recent conversations and active chats
    - Check what WhatsApp groups you are part of
    - Find who you recently talked to and the activity timestamp
    - Filter chats by name or keyword

    Parameters:
    - query: Optional case-insensitive name filter (e.g. "College", "Rahul", "Team")
    - limit: Maximum number of chats to return (default 15, max 30)
    """
    try:
        wa_client = make_whatsapp_client()
        async with wa_client:
            args = {
                "limit": min(max(limit, 1), 30),
                "include_last_message": False,
            }
            if query:
                args["query"] = query

            result = await asyncio.wait_for(
                wa_client.call_tool("list_chats", args),
                timeout=10,
            )

            if not result.content:
                return "No WhatsApp chats found."

            raw_text = result.content[0].text
            try:
                chats = json.loads(raw_text)
            except json.JSONDecodeError:
                return raw_text

            if not chats:
                return f"No WhatsApp chats found matching '{query}'." if query else "No WhatsApp chats found in cache."

            lines = [f"Recent WhatsApp Chats ({len(chats)}):"]
            for i, chat in enumerate(chats, 1):
                name = chat.get("name") or "Unknown"
                jid = chat.get("jid") or ""
                chat_type = "Group" if chat.get("is_group") else "Direct"
                last_time = chat.get("last_message_time") or "Unknown"

                lines.append(
                    f"{i}. [{chat_type}] {name}\n"
                    f"   Last Active: {last_time}\n"
                    f"   JID: {jid}"
                )

            return "\n\n".join(lines)

    except asyncio.TimeoutError:
        logger.error("WhatsApp list_chats timeout")
        return "WhatsApp MCP server timed out listing chats."
    except Exception as e:
        logger.exception("WhatsApp list_chats failed")
        return f"WhatsApp list chats error: {str(e)}"


@tool
async def whatsapp_read_messages(
    chat_name: str | None = None,
    query: str | None = None,
    limit: int = 10,
) -> str:
    """
    Read and search WhatsApp messages from contacts or groups.

    USE THIS TOOL to:
    - Read recent messages from a specific contact or group (e.g. chat_name="AI for Vizag" or chat_name="Mom")
    - Search message history for specific keywords (e.g. query="meeting" or query="project")
    - Read the latest incoming messages to summarize or answer questions about them

    Parameters:
    - chat_name: Optional name, phone number, or JID of the contact or group to read messages from
    - query: Optional text substring to search for within message contents
    - limit: Maximum number of messages to return (default 10, max 50)
    """
    try:
        wa_client = make_whatsapp_client()
        async with wa_client:
            chat_jid = None

            # Resolve chat_name to chat_jid if provided
            if chat_name:
                cleaned = chat_name.strip()
                if cleaned.endswith("@s.whatsapp.net") or cleaned.endswith("@g.us"):
                    chat_jid = cleaned
                elif is_phone_number(cleaned):
                    digits = normalize_phone_number(cleaned)
                    chat_jid = f"{digits}@s.whatsapp.net"
                else:
                    # Search chats first
                    chats_res = await asyncio.wait_for(
                        wa_client.call_tool("list_chats", {"query": cleaned, "limit": 5}),
                        timeout=10,
                    )
                    found_jid = None
                    if chats_res.content:
                        try:
                            chats = json.loads(chats_res.content[0].text)
                            if chats:
                                found_jid = chats[0].get("jid")
                        except Exception:
                            pass

                    # If no chat found, try search_contacts
                    if not found_jid:
                        contacts_res = await asyncio.wait_for(
                            wa_client.call_tool("search_contacts", {"query": cleaned}),
                            timeout=10,
                        )
                        if contacts_res.content:
                            try:
                                contacts = json.loads(contacts_res.content[0].text)
                                if contacts:
                                    c = contacts[0] if isinstance(contacts, list) else contacts
                                    phone = c.get("phone_number")
                                    if phone:
                                        found_jid = f"{phone}@s.whatsapp.net"
                                    elif c.get("jid"):
                                        found_jid = c.get("jid")
                            except Exception:
                                pass

                    if found_jid:
                        chat_jid = found_jid
                    else:
                        return f"Could not find a WhatsApp chat or contact matching '{chat_name}'."

            args = {
                "limit": min(max(limit, 1), 50),
            }
            if chat_jid:
                args["chat_jid"] = chat_jid
            if query:
                args["query"] = query

            result = await asyncio.wait_for(
                wa_client.call_tool("list_messages", args),
                timeout=15,
            )

            if not result.content or not result.content[0].text.strip():
                target = f" in '{chat_name}'" if chat_name else ""
                kw = f" containing '{query}'" if query else ""
                return f"No WhatsApp messages found{target}{kw}."

            return result.content[0].text

    except asyncio.TimeoutError:
        logger.error("WhatsApp read_messages timeout")
        return "WhatsApp MCP server timed out reading messages."
    except Exception as e:
        logger.exception("WhatsApp read_messages failed")
        return f"WhatsApp read messages error: {str(e)}"
