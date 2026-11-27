"""
whatsapp_tool.py — LangChain tool wrappers for the WhatsApp MCP sidecar.

Wrapped tools (10 total):
  - whatsapp_send_message      Send a text message
  - whatsapp_send_reply        Quote-reply to a specific message
  - whatsapp_send_reaction     React to a message with an emoji
  - whatsapp_send_file         Send an image / document / video / audio file
  - whatsapp_list_chats        List recent chats with preview
  - whatsapp_read_messages     Read / search message history
  - whatsapp_search_contacts   Search for a contact by name or phone
  - whatsapp_get_status        Check bridge health / connection status
  - whatsapp_mark_chat_read    Mark a chat's unread messages as read
  - whatsapp_create_group      Create a new WhatsApp group
"""

from langchain.tools import tool
from core_setup.mcp_client import make_whatsapp_client

import asyncio
import json
import logging
import re

logger = logging.getLogger(__name__)

PHONE_REGEX = re.compile(r"^\+?\d{10,15}$")

# Default MCP call timeout (seconds).  Most cached-read tools are fast;
# live-network tools (send_message, etc.) need a little more headroom.
_TIMEOUT_READ = 15
_TIMEOUT_WRITE = 20


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def is_phone_number(value: str) -> bool:
    """Return True when *value* looks like a phone number."""
    cleaned = value.replace(" ", "").replace("-", "")
    return bool(PHONE_REGEX.match(cleaned))


def normalize_phone_number(number: str) -> str:
    """
    Normalise an Indian phone number to its bare-digits form:

        +91 9542421642  →  919542421642
        91-9542421642   →  919542421642
        9542421642      →  919542421642   (10-digit: prepend 91)
    """
    digits = "".join(c for c in number if c.isdigit())
    if len(digits) == 10:
        digits = f"91{digits}"
    return digits


async def _resolve_jid(wa_client, contact_name: str) -> tuple[str | None, str | None]:
    """
    Try to resolve *contact_name* (name, phone, or JID) to a WhatsApp JID.

    Returns ``(jid, error_message)``.  Exactly one of the two will be None.
    """
    cleaned = contact_name.strip()

    # Already a JID
    if cleaned.endswith("@s.whatsapp.net") or cleaned.endswith("@g.us"):
        return cleaned, None

    # Raw phone number
    if is_phone_number(cleaned):
        digits = normalize_phone_number(cleaned)
        return f"{digits}@s.whatsapp.net", None

    # Try list_chats first (name search)
    try:
        chats_res = await asyncio.wait_for(
            wa_client.call_tool("list_chats", {"query": cleaned, "limit": 5}),
            timeout=_TIMEOUT_READ,
        )
        if chats_res.content:
            chats = json.loads(chats_res.content[0].text)
            if chats and chats[0].get("jid"):
                return chats[0]["jid"], None
    except (asyncio.TimeoutError, Exception):
        pass

    # Fallback: search_contacts
    try:
        contacts_res = await asyncio.wait_for(
            wa_client.call_tool("search_contacts", {"query": cleaned}),
            timeout=_TIMEOUT_READ,
        )
        if contacts_res.content:
            contacts = json.loads(contacts_res.content[0].text)
            if contacts:
                c = contacts[0] if isinstance(contacts, list) else contacts
                phone = c.get("phone_number")
                if phone:
                    return f"{phone}@s.whatsapp.net", None
                if c.get("jid"):
                    return c.get("jid"), None
    except (asyncio.TimeoutError, Exception):
        pass

    return None, (
        f"Could not find a WhatsApp contact or chat matching '{contact_name}'. "
        "Try using the phone number directly."
    )


def _first_text(result) -> str | None:
    """Return the first text content from an MCP result, or None."""
    if result and result.content:
        return result.content[0].text
    return None


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@tool
async def whatsapp_send_message(
    contact_name: str,
    message: str,
) -> str:
    """
    Send a WhatsApp text message to a contact or group.

    - contact_name: contact display-name, phone number (+91...), or WhatsApp JID.
      Phone numbers are the most reliable — always prefer them when known.
    - message: the text to send (supports basic WhatsApp formatting: *bold*, _italic_, ~strikethrough~, `mono`).

    Returns confirmation with timestamp on success, or an error message on failure.
    """
    logger.info("whatsapp_send_message: contact=%s", contact_name)
    try:
        wa_client = make_whatsapp_client()
        async with wa_client:
            jid, err = await _resolve_jid(wa_client, contact_name)
            if err:
                return err

            result = await asyncio.wait_for(
                wa_client.call_tool("send_message", {"recipient": jid, "message": message}),
                timeout=_TIMEOUT_WRITE,
            )
            text = _first_text(result)
            return text or f"Message sent to {contact_name}."

    except asyncio.TimeoutError:
        logger.error("whatsapp_send_message timeout")
        return "WhatsApp MCP server timed out while sending the message. Please try again."
    except Exception as e:
        logger.exception("whatsapp_send_message failed")
        return f"WhatsApp send error: {e}"


@tool
async def whatsapp_send_reply(
    contact_name: str,
    message_id: str,
    reply_text: str,
) -> str:
    """
    Send a WhatsApp reply that visually quotes a previous message.

    - contact_name: contact display-name, phone number, or JID of the chat.
    - message_id: the ID of the message to quote (obtain via whatsapp_read_messages).
    - reply_text: the text of your reply.

    Use this instead of whatsapp_send_message when you want the reply to visually
    reference a specific earlier message (e.g. answering a question in a group chat).
    """
    logger.info("whatsapp_send_reply: contact=%s msg_id=%s", contact_name, message_id)
    try:
        wa_client = make_whatsapp_client()
        async with wa_client:
            jid, err = await _resolve_jid(wa_client, contact_name)
            if err:
                return err

            result = await asyncio.wait_for(
                wa_client.call_tool(
                    "send_reply",
                    {"chat_jid": jid, "target_message_id": message_id, "body": reply_text},
                ),
                timeout=_TIMEOUT_WRITE,
            )
            text = _first_text(result)
            return text or f"Reply sent to {contact_name}."

    except asyncio.TimeoutError:
        logger.error("whatsapp_send_reply timeout")
        return "WhatsApp MCP server timed out. Please try again."
    except Exception as e:
        logger.exception("whatsapp_send_reply failed")
        return f"WhatsApp reply error: {e}"


@tool
async def whatsapp_send_reaction(
    contact_name: str,
    message_id: str,
    emoji: str,
) -> str:
    """
    Add or replace an emoji reaction on a WhatsApp message.

    - contact_name: contact display-name, phone number, or JID.
    - message_id: the ID of the message to react to (obtain via whatsapp_read_messages).
    - emoji: a single emoji character, e.g. "👍", "❤️", "😂". Pass "" to remove your reaction.

    Returns confirmation on success.
    """
    logger.info("whatsapp_send_reaction: contact=%s emoji=%s", contact_name, emoji)
    try:
        wa_client = make_whatsapp_client()
        async with wa_client:
            jid, err = await _resolve_jid(wa_client, contact_name)
            if err:
                return err

            result = await asyncio.wait_for(
                wa_client.call_tool(
                    "send_reaction",
                    {"chat_jid": jid, "message_id": message_id, "emoji": emoji},
                ),
                timeout=_TIMEOUT_WRITE,
            )
            text = _first_text(result)
            action = "removed" if not emoji else f"reacted with {emoji}"
            return text or f"Successfully {action} on message {message_id}."

    except asyncio.TimeoutError:
        logger.error("whatsapp_send_reaction timeout")
        return "WhatsApp MCP server timed out. Please try again."
    except Exception as e:
        logger.exception("whatsapp_send_reaction failed")
        return f"WhatsApp reaction error: {e}"


@tool
async def whatsapp_send_file(
    contact_name: str,
    file_path: str,
    caption: str = "",
) -> str:
    """
    Send a file (image, PDF, video, audio, etc.) as a WhatsApp attachment.

    - contact_name: contact display-name, phone number, or JID.
    - file_path: absolute path to the file on the server filesystem, e.g. "/tmp/report.pdf".
      The WhatsApp MCP sidecar must be able to read this path (files in /tmp and /app/uploads
      are accessible from the container).
    - caption: optional text caption shown below the attachment (leave blank for none).

    Returns confirmation with file details on success.
    """
    logger.info("whatsapp_send_file: contact=%s file=%s", contact_name, file_path)
    try:
        wa_client = make_whatsapp_client()
        async with wa_client:
            jid, err = await _resolve_jid(wa_client, contact_name)
            if err:
                return err

            args: dict = {"recipient": jid, "media_path": file_path}
            if caption:
                args["caption"] = caption

            result = await asyncio.wait_for(
                wa_client.call_tool("send_file", args),
                timeout=_TIMEOUT_WRITE * 2,  # file upload may be slower
            )
            text = _first_text(result)
            return text or f"File '{file_path}' sent to {contact_name}."

    except asyncio.TimeoutError:
        logger.error("whatsapp_send_file timeout")
        return "WhatsApp MCP server timed out while uploading the file. Please try again."
    except Exception as e:
        logger.exception("whatsapp_send_file failed")
        return f"WhatsApp send-file error: {e}"


@tool
async def whatsapp_list_chats(
    limit: int = 20,
    query: str = "",
) -> str:
    """
    List recent WhatsApp chats with a last-message preview.

    - limit: how many chats to return (default 20, max 50).
    - query: optional name filter to narrow results (e.g. "Mom", "AI for Vizag").

    Returns a numbered list of chats with their last active time, type (contact/group),
    and a preview of the most recent message.
    """
    logger.info("whatsapp_list_chats: limit=%d query=%r", limit, query)
    try:
        wa_client = make_whatsapp_client()
        async with wa_client:
            args: dict = {"limit": min(max(limit, 1), 50)}
            if query:
                args["query"] = query

            result = await asyncio.wait_for(
                wa_client.call_tool("list_chats", args),
                timeout=_TIMEOUT_READ,
            )

            if not result.content or not result.content[0].text.strip():
                return "No WhatsApp chats found."

            raw = result.content[0].text
            try:
                chats = json.loads(raw)
            except json.JSONDecodeError:
                return raw  # already formatted text

            if not chats:
                return "No WhatsApp chats found."

            lines = []
            for i, chat in enumerate(chats, 1):
                name = chat.get("name") or chat.get("jid", "Unknown")
                jid = chat.get("jid", "")
                chat_type = "Group" if jid.endswith("@g.us") else "Contact"
                last_time = chat.get("last_message_time", "unknown")[:16].replace("T", " ")

                # Last message preview
                msg_line = ""
                last_msg = chat.get("last_message", "")
                if last_msg:
                    sender = "You" if chat.get("is_last_message_from_me") else "Them"
                    last_msg = last_msg.replace("\n", " ").strip()
                    if len(last_msg) > 80:
                        last_msg = last_msg[:77] + "..."
                    msg_line = f'\n   Last ({sender}): "{last_msg}"'

                lines.append(
                    f"{i}. [{chat_type}] {name} — {last_time}{msg_line}"
                )

            return "\n\n".join(lines)

    except asyncio.TimeoutError:
        logger.error("whatsapp_list_chats timeout")
        return "WhatsApp MCP server timed out listing chats. Please try again."
    except Exception as e:
        logger.exception("whatsapp_list_chats failed")
        return f"WhatsApp list chats error: {e}"


@tool
async def whatsapp_read_messages(
    chat_name: str | None = None,
    query: str | None = None,
    limit: int = 10,
) -> str:
    """
    Read and search WhatsApp message history.

    - chat_name: name, phone number, or JID of the chat/group to read from.
      If omitted, searches across all chats.
    - query: optional keyword to search for within message text.
    - limit: number of messages to return (default 10, max 50).

    Use this to:
    - Read recent messages from a contact or group ("chat_name='Mom'")
    - Search for a topic across all messages ("query='meeting link'")
    - Summarise the latest messages in a group chat
    """
    logger.info("whatsapp_read_messages: chat=%r query=%r limit=%d", chat_name, query, limit)
    try:
        wa_client = make_whatsapp_client()
        async with wa_client:
            chat_jid = None

            if chat_name:
                jid, err = await _resolve_jid(wa_client, chat_name)
                if err:
                    return err
                chat_jid = jid

            args: dict = {"limit": min(max(limit, 1), 50)}
            if chat_jid:
                args["chat_jid"] = chat_jid
            if query:
                args["query"] = query

            result = await asyncio.wait_for(
                wa_client.call_tool("list_messages", args),
                timeout=_TIMEOUT_READ,
            )

            if not result.content or not result.content[0].text.strip():
                target = f" in '{chat_name}'" if chat_name else ""
                kw = f" containing '{query}'" if query else ""
                return f"No WhatsApp messages found{target}{kw}."

            return result.content[0].text

    except asyncio.TimeoutError:
        logger.error("whatsapp_read_messages timeout")
        return "WhatsApp MCP server timed out reading messages. Please try again."
    except Exception as e:
        logger.exception("whatsapp_read_messages failed")
        return f"WhatsApp read messages error: {e}"


@tool
async def whatsapp_search_contacts(
    query: str,
) -> str:
    """
    Search the WhatsApp contact cache by name or partial phone number.

    - query: name fragment or partial phone number, e.g. "Ravi", "9876".

    Returns a list of matching contacts with their name and phone number.
    Useful before sending a message when you're unsure of the exact contact name.
    """
    logger.info("whatsapp_search_contacts: query=%r", query)
    try:
        wa_client = make_whatsapp_client()
        async with wa_client:
            result = await asyncio.wait_for(
                wa_client.call_tool("search_contacts", {"query": query}),
                timeout=_TIMEOUT_READ,
            )

            if not result.content or not result.content[0].text.strip():
                return f"No contacts found matching '{query}'."

            raw = result.content[0].text
            try:
                contacts = json.loads(raw)
            except json.JSONDecodeError:
                return raw

            if not contacts:
                return f"No contacts found matching '{query}'."

            lines = []
            for c in (contacts if isinstance(contacts, list) else [contacts]):
                name = c.get("name") or "Unknown"
                phone = c.get("phone_number") or c.get("jid") or "—"
                lines.append(f"• {name} — {phone}")

            return "\n".join(lines)

    except asyncio.TimeoutError:
        logger.error("whatsapp_search_contacts timeout")
        return "WhatsApp MCP server timed out. Please try again."
    except Exception as e:
        logger.exception("whatsapp_search_contacts failed")
        return f"WhatsApp search contacts error: {e}"


@tool
async def whatsapp_get_status() -> str:
    """
    Check the current WhatsApp bridge connection status.

    Returns whether the bridge is connected to WhatsApp servers, the linked phone
    number, and when it last synced. Useful for diagnosing why messages may be
    failing or delayed before attempting to send.
    """
    logger.info("whatsapp_get_status")
    try:
        wa_client = make_whatsapp_client()
        async with wa_client:
            result = await asyncio.wait_for(
                wa_client.call_tool("get_status", {}),
                timeout=10,
            )
            text = _first_text(result)
            return text or "WhatsApp bridge status unknown."

    except asyncio.TimeoutError:
        logger.error("whatsapp_get_status timeout")
        return "WhatsApp MCP server timed out checking status."
    except Exception as e:
        logger.exception("whatsapp_get_status failed")
        return f"WhatsApp status error: {e}"


@tool
async def whatsapp_mark_chat_read(
    contact_name: str,
) -> str:
    """
    Mark all unread messages in a WhatsApp chat as read (clears the unread badge).

    - contact_name: contact display-name, phone number, or JID.

    Senders do NOT receive read receipts from this action unless you have
    read-receipts enabled in your WhatsApp privacy settings.
    """
    logger.info("whatsapp_mark_chat_read: contact=%s", contact_name)
    try:
        wa_client = make_whatsapp_client()
        async with wa_client:
            jid, err = await _resolve_jid(wa_client, contact_name)
            if err:
                return err

            result = await asyncio.wait_for(
                wa_client.call_tool("mark_chat_read", {"chat_jid": jid}),
                timeout=_TIMEOUT_WRITE,
            )
            text = _first_text(result)
            return text or f"Marked chat with {contact_name} as read."

    except asyncio.TimeoutError:
        logger.error("whatsapp_mark_chat_read timeout")
        return "WhatsApp MCP server timed out. Please try again."
    except Exception as e:
        logger.exception("whatsapp_mark_chat_read failed")
        return f"WhatsApp mark-read error: {e}"


@tool
async def whatsapp_create_group(
    name: str,
    participants: list[str],
) -> str:
    """
    Create a new WhatsApp group.

    - name: the display name for the group.
    - participants: list of phone numbers (with country code) or WhatsApp JIDs
      to add as initial members, e.g. ["919542421642", "917670815170"].

    Returns the new group's JID and invite link on success.
    The user creating the group is automatically added as admin.
    """
    logger.info("whatsapp_create_group: name=%r participants=%s", name, participants)
    try:
        wa_client = make_whatsapp_client()
        async with wa_client:
            # Normalise participant list to JIDs
            jids = []
            for p in participants:
                p = p.strip()
                if p.endswith("@s.whatsapp.net") or p.endswith("@g.us"):
                    jids.append(p)
                elif is_phone_number(p):
                    jids.append(f"{normalize_phone_number(p)}@s.whatsapp.net")
                else:
                    return (
                        f"Cannot determine JID for participant '{p}'. "
                        "Please provide phone numbers."
                    )

            result = await asyncio.wait_for(
                wa_client.call_tool(
                    "create_group",
                    {"name": name, "participants": jids},
                ),
                timeout=_TIMEOUT_WRITE,
            )
            text = _first_text(result)
            return text or f"Group '{name}' created successfully."

    except asyncio.TimeoutError:
        logger.error("whatsapp_create_group timeout")
        return "WhatsApp MCP server timed out. Please try again."
    except Exception as e:
        logger.exception("whatsapp_create_group failed")
        return f"WhatsApp create group error: {e}"
