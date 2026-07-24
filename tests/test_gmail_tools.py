import base64
from email import policy
from email.parser import BytesParser

import pytest

from app.tools.gmail_tools import _build_raw_email


def _decode_message(raw_message: str):
    decoded = base64.urlsafe_b64decode(raw_message.encode("utf-8"))
    return BytesParser(policy=policy.default).parsebytes(decoded)


def test_build_raw_email_preserves_valid_content():
    raw_message = _build_raw_email(
        to="recruiter@example.com",
        subject="Application — ML Engineer",
        body="Hello,\n\nPlease find my application.",
    )

    message = _decode_message(raw_message)
    assert message["To"] == "recruiter@example.com"
    assert message["Subject"] == "Application — ML Engineer"
    assert "Please find my application." in message.get_content()


def test_build_raw_email_rejects_header_injection():
    with pytest.raises(ValueError, match="newline"):
        _build_raw_email(
            to="recruiter@example.com",
            subject="Application\nBcc: attacker@example.com",
            body="Hello",
        )


def test_build_raw_email_rejects_invalid_recipient():
    with pytest.raises(ValueError, match="Invalid email address"):
        _build_raw_email(
            to="not-an-email",
            subject="Application",
            body="Hello",
        )


def test_build_raw_email_rejects_empty_body():
    with pytest.raises(ValueError, match="body cannot be empty"):
        _build_raw_email(
            to="recruiter@example.com",
            subject="Application",
            body="   ",
        )
