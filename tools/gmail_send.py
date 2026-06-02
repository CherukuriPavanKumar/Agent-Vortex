from typing import Annotated, Optional
import base64

from email.message import EmailMessage

from langchain_core.tools import tool

from core_setup.google_service import (
    get_gmail_service,
    GoogleAuthError,
)


@tool
def gmail_send(
    to: Annotated[
        str,
        "Primary recipient email address(es) separated by commas",
    ],
    subject: Annotated[
        str,
        "Email subject line",
    ],
    body: Annotated[
        str,
        "Plain text email body",
    ],
    cc: Annotated[
        Optional[str],
        "CC email address(es) separated by commas",
    ] = None,
    bcc: Annotated[
        Optional[str],
        "BCC email address(es) separated by commas",
    ] = None,
) -> str:
    """
    Send an email using Gmail.
    """

    try:
        service = get_gmail_service()

        message = EmailMessage()

        message["To"] = to
        message["Subject"] = subject

        if cc:
            message["Cc"] = cc

        if bcc:
            message["Bcc"] = bcc

        message.set_content(body)

        raw_message = base64.urlsafe_b64encode(
            message.as_bytes()
        ).decode()

        result = (
            service.users()
            .messages()
            .send(
                userId="me",
                body={
                    "raw": raw_message,
                },
            )
            .execute()
        )

        message_id = result.get("id", "unknown")

        return (
            f"Email sent successfully.\n"
            f"To: {to}\n"
            f"Subject: {subject}\n"
            f"Message ID: {message_id}"
        )

    except GoogleAuthError as e:
        return f"Google authentication error: {e}"

    except Exception as e:
        return f"Gmail send failed: {e}"