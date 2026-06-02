from typing import Annotated
import base64

from langchain_core.tools import tool

from core_setup.google_service import (
    get_gmail_service,
    GoogleAuthError,
)


def parse_parts(parts) -> str:
    """Recursively extract plain-text content from Gmail MIME parts."""
    body = ""

    for part in parts:
        mime_type = part.get("mimeType")

        if mime_type == "text/plain":
            data = part.get("body", {}).get("data")

            if data:
                body += base64.urlsafe_b64decode(data).decode(
                    "utf-8",
                    errors="ignore",
                )

        elif "parts" in part:
            body += parse_parts(part["parts"])

    return body


@tool
def gmail_read(
    query: Annotated[
        str,
        "Gmail search query (e.g. is:unread, from:amazon, newer_than:7d)",
    ] = "",
    max_results: Annotated[
        int,
        "Maximum number of emails to fetch",
    ] = 10,
) -> str:
    """
    Read emails from Gmail using Gmail search syntax.
    """

    try:
        service = get_gmail_service()

        results = (
            service.users()
            .messages()
            .list(
                userId="me",
                q=query,
                maxResults=max_results,
            )
            .execute()
        )

        messages = results.get("messages", [])

        if not messages:
            return "No emails found."

        email_outputs = []

        for msg in messages:
            message = (
                service.users()
                .messages()
                .get(
                    userId="me",
                    id=msg["id"],
                    format="full",
                )
                .execute()
            )

            payload = message.get("payload", {})
            headers = payload.get("headers", [])

            subject = "No Subject"
            sender = "Unknown Sender"
            date = "Unknown Date"

            for header in headers:
                name = header.get("name", "").lower()

                if name == "subject":
                    subject = header.get("value", subject)

                elif name == "from":
                    sender = header.get("value", sender)

                elif name == "date":
                    date = header.get("value", date)

            body_text = ""

            if "parts" in payload:
                body_text = parse_parts(payload["parts"])

            else:
                data = payload.get("body", {}).get("data")

                if data:
                    body_text = base64.urlsafe_b64decode(
                        data
                    ).decode(
                        "utf-8",
                        errors="ignore",
                    )

            if not body_text.strip():
                body_text = message.get(
                    "snippet",
                    "No content available.",
                )

            email_outputs.append(
                "\n".join(
                    [
                        f"ID: {msg['id']}",
                        f"From: {sender}",
                        f"Date: {date}",
                        f"Subject: {subject}",
                        "",
                        "Body:",
                        body_text[:2000],
                        "-" * 60,
                    ]
                )
            )

        return "Fetched Emails:\n\n" + "\n".join(email_outputs)

    except GoogleAuthError as e:
        return f"Google authentication error: {e}"

    except Exception as e:
        return f"Gmail read failed: {e}"