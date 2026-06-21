import logging
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from config.settings import GMAIL_CREDENTIALS_FILE, GMAIL_TOKEN_FILE

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
]

CREDENTIALS_FILE = Path(GMAIL_CREDENTIALS_FILE)
TOKEN_FILE       = Path(GMAIL_TOKEN_FILE)


def get_gmail_service():
    if not CREDENTIALS_FILE.exists():
        raise FileNotFoundError(
            f"Gmail credentials file not found at {CREDENTIALS_FILE}. "
            "Download it from Google Cloud Console > APIs & Services > Credentials "
            "and save it as data/gmail_credentials.json"
        )

    creds = None

    if TOKEN_FILE.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
        except Exception as e:
            logging.warning(f"[Gmail][Auth] Could not load token file: {e}; will re-authenticate.")
            creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                logging.info("[Gmail][Auth] Token refreshed successfully.")
            except Exception as e:
                logging.warning(f"[Gmail][Auth] Token refresh failed: {e}; re-authenticating.")
                creds = None

        if not creds:
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
            logging.info("[Gmail][Auth] New OAuth token obtained.")

        TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_FILE.write_text(creds.to_json())
        logging.info(f"[Gmail][Auth] Token saved to {TOKEN_FILE}")

    return build("gmail", "v1", credentials=creds)