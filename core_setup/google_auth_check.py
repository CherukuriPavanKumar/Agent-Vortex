"""
Shared Google OAuth credential checker.

Used at startup to determine whether Gmail and Calendar tools should be
registered. If credentials.json is missing we disable Google tools gracefully
rather than letting them crash at invocation time.
"""

import os

# Single authoritative scope list used by ALL Google tool files.
# Using one shared set prevents stale-token re-auth loops: if each tool file
# defined its own subset, a token.pickle written by one tool would fail the
# has_scopes() check in another, triggering InstalledAppFlow.run_local_server()
# which opens a browser — crashing silently in Docker / headless environments.
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar",
]


def is_google_configured() -> bool:
    """
    Return True if the minimum Google OAuth files are present.

    credentials.json  — required: the downloaded OAuth client secret from
                        Google Cloud Console.
    token.pickle      — optional on first run; generated after first OAuth
                        flow completes. Without it the tool will attempt a
                        browser-based flow, which fails inside Docker.

    We only require credentials.json here. Tools will handle missing
    token.pickle themselves (they trigger a browser auth flow locally, which
    only works on a dev machine, not in Docker).
    """
    return os.path.isfile("credentials.json")


GOOGLE_SETUP_INSTRUCTIONS = """
╔══════════════════════════════════════════════════════════════════╗
║           Gmail & Google Calendar Setup Instructions             ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  Gmail and Calendar tools are DISABLED because credentials.json  ║
║  was not found.                                                  ║
║                                                                  ║
║  To enable them:                                                 ║
║                                                                  ║
║  1. Go to https://console.cloud.google.com/                      ║
║  2. Create a project → Enable Gmail API + Google Calendar API    ║
║  3. OAuth consent screen → External → Add your email as tester  ║
║  4. Credentials → Create OAuth client ID → Desktop App           ║
║  5. Download the JSON → save as credentials.json in repo root    ║
║  6. Run locally once (not in Docker):                            ║
║       python main.py                                             ║
║     A browser window opens — authorize the app.                  ║
║     token.pickle is created automatically.                       ║
║  7. Restart the application.                                     ║
║                                                                  ║
║  See README.md → "Gmail & Calendar Setup" for full details.      ║
╚══════════════════════════════════════════════════════════════════╝
""".strip()
