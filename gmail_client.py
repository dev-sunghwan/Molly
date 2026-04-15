"""
gmail_client.py — Gmail API authentication for Molly.

This module intentionally uses a separate token file from calendar_client.py
so Gmail and Calendar OAuth state can be managed independently.
"""
from __future__ import annotations

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

import config

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def authenticate():
    """
    Authenticate with Gmail using a dedicated token file.
    - Reuses the same OAuth client credentials file as Calendar by default.
    - Stores Gmail consent state in gmail_token.json so Gmail and Calendar
      permissions can evolve independently.
    Returns a Gmail API service object.
    """
    creds = None

    if config.GMAIL_TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(config.GMAIL_TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(config.GMAIL_CREDENTIALS_PATH),
                SCOPES,
            )
            creds = flow.run_local_server(port=0)

        config.GMAIL_TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")

    return build("gmail", "v1", credentials=creds)
