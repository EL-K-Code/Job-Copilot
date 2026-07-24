from __future__ import annotations

import base64
from email.message import EmailMessage
from email.utils import getaddresses
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from app.config import settings


GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/calendar.events",
]


def google_token_exists() -> bool:
    return settings.google_token_path.exists()


def get_google_credentials(interactive: bool = False) -> Credentials:
    token_path = settings.google_token_path
    token_path.parent.mkdir(parents=True, exist_ok=True)

    creds: Credentials | None = None

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(
            str(token_path),
            GOOGLE_SCOPES,
        )

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_path.write_text(creds.to_json(), encoding="utf-8")
        return creds

    if not interactive:
        raise RuntimeError(
            "No valid Google token found. Run Google auth bootstrap first."
        )

    credentials_file = settings.google_client_secret_path
    if not credentials_file.exists():
        raise FileNotFoundError(
            f"Google OAuth client file not found: {credentials_file}"
        )

    flow = InstalledAppFlow.from_client_secrets_file(
        str(credentials_file),
        GOOGLE_SCOPES,
    )

    creds = flow.run_local_server(
        host="127.0.0.1",
        port=8080,
        open_browser=True,
    )

    token_path.write_text(creds.to_json(), encoding="utf-8")
    return creds


def build_gmail_service(interactive: bool = False):
    creds = get_google_credentials(interactive=interactive)
    return build("gmail", "v1", credentials=creds)


def _validate_header_value(name: str, value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{name} cannot be empty.")
    if "\r" in normalized or "\n" in normalized:
        raise ValueError(f"{name} cannot contain newline characters.")
    return normalized


def _validate_address_list(name: str, value: str | None) -> str | None:
    if value is None:
        return None

    normalized = _validate_header_value(name, value)
    parsed_addresses = getaddresses([normalized])
    if not parsed_addresses:
        raise ValueError(f"{name} must contain at least one valid email address.")

    for _display_name, address in parsed_addresses:
        local_part, separator, domain = address.rpartition("@")
        if not separator or not local_part or "." not in domain:
            raise ValueError(f"Invalid email address in {name}: {address or value}")

    return normalized


def _build_raw_email(
    to: str,
    subject: str,
    body: str,
    cc: str | None = None,
    bcc: str | None = None,
) -> str:
    validated_to = _validate_address_list("to", to)
    validated_cc = _validate_address_list("cc", cc)
    validated_bcc = _validate_address_list("bcc", bcc)
    validated_subject = _validate_header_value("subject", subject)
    validated_body = body.strip()

    if not validated_body:
        raise ValueError("body cannot be empty.")

    message = EmailMessage()
    message["To"] = validated_to
    message["Subject"] = validated_subject

    if validated_cc:
        message["Cc"] = validated_cc
    if validated_bcc:
        message["Bcc"] = validated_bcc

    message.set_content(validated_body)

    raw_bytes = message.as_bytes()
    return base64.urlsafe_b64encode(raw_bytes).decode("utf-8")


def create_gmail_draft(
    to: str,
    subject: str,
    body: str,
    cc: str | None = None,
    bcc: str | None = None,
) -> dict[str, Any]:
    raw_message = _build_raw_email(
        to=to,
        subject=subject,
        body=body,
        cc=cc,
        bcc=bcc,
    )
    service = build_gmail_service(interactive=False)

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
