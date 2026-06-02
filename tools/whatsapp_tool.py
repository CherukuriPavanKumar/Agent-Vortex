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