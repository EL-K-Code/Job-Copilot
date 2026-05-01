from __future__ import annotations

import base64
from email.message import EmailMessage
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from app.config import settings


GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.compose",
]


def gmail_token_exists() -> bool:
    return settings.google_token_path.exists()


def get_gmail_credentials(interactive: bool = False) -> Credentials:
    """
    Load Gmail OAuth credentials from disk, refresh them if needed,
    or trigger an interactive OAuth flow if allowed.
    """
    token_path = settings.google_token_path
    token_path.parent.mkdir(parents=True, exist_ok=True)

    creds: Credentials | None = None

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(
            str(token_path),
            GMAIL_SCOPES,
        )

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_path.write_text(creds.to_json(), encoding="utf-8")
        return creds

    if not interactive:
        raise RuntimeError(
            "No valid Gmail token found. Run Gmail auth bootstrap first."
        )

    credentials_file = settings.google_client_secret_path
    if not credentials_file.exists():
        raise FileNotFoundError(
            f"Google OAuth client file not found: {credentials_file}"
        )

    flow = InstalledAppFlow.from_client_secrets_file(
        str(credentials_file),
        GMAIL_SCOPES,
    )

    # Useful on remote/terminal-first environments.
    creds = flow.run_local_server(
    host="127.0.0.1",
    port=8090,
    open_browser=False,
)

    token_path.write_text(creds.to_json(), encoding="utf-8")
    return creds


def build_gmail_service(interactive: bool = False):
    creds = get_gmail_credentials(interactive=interactive)
    return build("gmail", "v1", credentials=creds)


def _build_raw_email(
    to: str,
    subject: str,
    body: str,
    cc: str | None = None,
    bcc: str | None = None,
) -> str:
    """
    Build a MIME email and return its base64url-encoded raw representation.
    """
    message = EmailMessage()
    message["To"] = to
    message["Subject"] = subject

    if cc:
        message["Cc"] = cc
    if bcc:
        message["Bcc"] = bcc

    message.set_content(body)

    raw_bytes = message.as_bytes()
    raw_b64 = base64.urlsafe_b64encode(raw_bytes).decode("utf-8")
    return raw_b64


def create_gmail_draft(
    to: str,
    subject: str,
    body: str,
    cc: str | None = None,
    bcc: str | None = None,
) -> dict[str, Any]:
    """
    Create a Gmail draft in the authenticated user's mailbox.
    """
    service = build_gmail_service(interactive=False)

    raw_message = _build_raw_email(
        to=to,
        subject=subject,
        body=body,
        cc=cc,
        bcc=bcc,
    )

    draft_body = {
        "message": {
            "raw": raw_message,
        }
    }

    draft = (
        service.users()
        .drafts()
        .create(userId="me", body=draft_body)
        .execute()
    )

    return {
        "draft_id": draft.get("id", ""),
        "message_id": draft.get("message", {}).get("id", ""),
    }