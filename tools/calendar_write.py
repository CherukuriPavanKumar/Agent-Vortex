from typing import Annotated, Optional

from langchain_core.tools import tool

from core_setup.google_service import (
    get_calendar_service,
    GoogleAuthError,
)


@tool
def calendar_write(
    summary: Annotated[
        str,
        "The title or summary of the event",
    ],
    start_time: Annotated[
        str,
        "Start time in ISO 8601 format (e.g. 2026-05-29T10:00:00-07:00)",
    ],
    end_time: Annotated[
        str,
        "End time in ISO 8601 format (e.g. 2026-05-29T11:00:00-07:00)",
    ],
    description: Annotated[
        Optional[str],
        "Description of the event",
    ] = None,
    attendees: Annotated[
        Optional[str],
        "Comma-separated attendee email addresses",
    ] = None,
    location: Annotated[
        Optional[str],
        "Location of the event",
    ] = None,
) -> str:
    """
    Create a Google Calendar event.

    start_time and end_time must be valid ISO 8601 timestamps
    including timezone offsets.
    """

    try:
        service = get_calendar_service()

        event_body = {
            "summary": summary,
            "start": {
                "dateTime": start_time,
            },
            "end": {
                "dateTime": end_time,
            },
        }

        if description:
            event_body["description"] = description

        if location:
            event_body["location"] = location

        if attendees:
            attendee_list = [
                {"email": email.strip()}
                for email in attendees.split(",")
                if email.strip()
            ]

            if attendee_list:
                event_body["attendees"] = attendee_list

        event = (
            service.events()
            .insert(
                calendarId="primary",
                body=event_body,
                sendUpdates="all",
            )
            .execute()
        )

        event_link = event.get("htmlLink", "No link available")
        event_id = event.get("id", "Unknown")

        return (
            "Event created successfully.\n"
            f"Title: {summary}\n"
            f"Event ID: {event_id}\n"
            f"Link: {event_link}"
        )

    except GoogleAuthError as e:
        return f"Google authentication error: {e}"

    except Exception as e:
        return f"Calendar event creation failed: {e}"