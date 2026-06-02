from typing import Annotated, Optional
import datetime

from langchain_core.tools import tool

from core_setup.google_service import (
    get_calendar_service,
    GoogleAuthError,
)


@tool
def calendar_read(
    query: Annotated[
        Optional[str],
        "Search query to filter events",
    ] = None,
    max_results: Annotated[
        int,
        "Maximum number of events to return",
    ] = 10,
    days_ahead: Annotated[
        int,
        "Number of days ahead to search",
    ] = 7,
) -> str:
    """
    Fetch upcoming events from the user's primary Google Calendar.
    """

    try:
        service = get_calendar_service()

        now = datetime.datetime.now(datetime.timezone.utc)

        time_min = (
            now.isoformat()
            .replace("+00:00", "Z")
        )

        time_max = (
            now + datetime.timedelta(days=days_ahead)
        ).isoformat().replace("+00:00", "Z")

        kwargs = {
            "calendarId": "primary",
            "timeMin": time_min,
            "timeMax": time_max,
            "maxResults": max_results,
            "singleEvents": True,
            "orderBy": "startTime",
        }

        if query:
            kwargs["q"] = query

        events_result = (
            service.events()
            .list(**kwargs)
            .execute()
        )

        events = events_result.get("items", [])

        if not events:
            return "No upcoming events found."

        output = []

        for event in events:
            start = event["start"].get(
                "dateTime",
                event["start"].get("date"),
            )

            end = event["end"].get(
                "dateTime",
                event["end"].get("date"),
            )

            summary = event.get(
                "summary",
                "No Title",
            )

            description = event.get(
                "description",
                "No Description",
            )

            location = event.get(
                "location",
                "No Location",
            )

            output.append(
                "\n".join(
                    [
                        f"Event: {summary}",
                        f"Start: {start}",
                        f"End: {end}",
                        f"Location: {location}",
                        f"Description: {description}",
                        "-" * 60,
                    ]
                )
            )

        return (
            f"Upcoming Calendar Events "
            f"(Next {days_ahead} Days):\n\n"
            + "\n".join(output)
        )

    except GoogleAuthError as e:
        return f"Google authentication error: {e}"

    except Exception as e:
        return f"Calendar read failed: {e}"