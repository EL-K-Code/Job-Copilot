import pytest
from pydantic import ValidationError

from app.schemas import ApplicationRecord, EmailDraft


def test_application_record_normalizes_required_text():
    record = ApplicationRecord(
        company="  Example Labs  ",
        role="  ML Engineer  ",
        source="  manual  ",
    )

    assert record.company == "Example Labs"
    assert record.role == "ML Engineer"
    assert record.source == "manual"


def test_application_record_rejects_invalid_reminder_date():
    with pytest.raises(ValidationError, match="YYYY-MM-DD"):
        ApplicationRecord(
            company="Example Labs",
            role="ML Engineer",
            reminder_date="15/08/2026",
        )


def test_email_draft_rejects_empty_content():
    with pytest.raises(ValidationError, match="subject"):
        EmailDraft(subject=" ", body="Hello")

    with pytest.raises(ValidationError, match="body"):
        EmailDraft(subject="Application", body=" ")
