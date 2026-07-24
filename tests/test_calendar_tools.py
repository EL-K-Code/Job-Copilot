import pytest

from app.tools.calendar_tools import build_followup_event_payload


def test_followup_payload_uses_expected_schedule_and_timezone():
    payload = build_followup_event_payload(
        company="Example Labs",
        role="ML Engineer",
        followup_date="2026-08-15",
        timezone_str="Europe/Paris",
    )

    assert payload["summary"] == "Follow up — Example Labs — ML Engineer"
    assert payload["start_iso"] == "2026-08-15T09:00:00"
    assert payload["end_iso"] == "2026-08-15T09:30:00"
    assert payload["timezone_str"] == "Europe/Paris"


def test_followup_payload_rejects_invalid_date_format():
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        build_followup_event_payload(
            company="Example Labs",
            role="ML Engineer",
            followup_date="15/08/2026",
        )


def test_followup_payload_rejects_missing_identity_fields():
    with pytest.raises(ValueError, match="company"):
        build_followup_event_payload(
            company=" ",
            role="ML Engineer",
            followup_date="2026-08-15",
        )
