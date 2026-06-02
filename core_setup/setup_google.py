from pathlib import Path
import pickle

from google_auth_oauthlib.flow import InstalledAppFlow

from core_setup.google_auth_check import GOOGLE_SCOPES


CREDENTIALS_FILE = Path("credentials.json")
TOKEN_FILE = Path("token.pickle")


def main():
    if not CREDENTIALS_FILE.exists():
        raise FileNotFoundError(
            "credentials.json not found."
        )

    flow = InstalledAppFlow.from_client_secrets_file(
        str(CREDENTIALS_FILE),
        GOOGLE_SCOPES,
    )

    creds = flow.run_local_server(port=0)

    with TOKEN_FILE.open("wb") as f:
        pickle.dump(creds, f)

    print("✓ token.pickle created")


if __name__ == "__main__":
    main()