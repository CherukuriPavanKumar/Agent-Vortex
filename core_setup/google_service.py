from pathlib import Path
import pickle

from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from core_setup.google_auth_check import GOOGLE_SCOPES


CREDENTIALS_FILE = Path("credentials.json")
TOKEN_FILE = Path("token.pickle")


class GoogleAuthError(Exception):
    pass


def get_google_credentials():
    creds = None

    if TOKEN_FILE.exists():
        with TOKEN_FILE.open("rb") as f:
            creds = pickle.load(f)

    if creds and not creds.has_scopes(GOOGLE_SCOPES):
        raise GoogleAuthError(
            "Stored token is missing required scopes. "
            "Delete token.pickle and re-run setup."
        )

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())

        with TOKEN_FILE.open("wb") as f:
            pickle.dump(creds, f)

    if not creds:
        raise GoogleAuthError(
            "Google authentication not completed. "
            "Run: python core_setup/setup_google.py"
)
    return creds


def get_gmail_service():
    creds = get_google_credentials()
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def get_calendar_service():
    creds = get_google_credentials()
    return build("calendar", "v3", credentials=creds, cache_discovery=False)