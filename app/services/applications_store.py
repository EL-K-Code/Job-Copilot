from __future__ import annotations

import json
from datetime import datetime, timezone

from app.config import settings
from app.schemas import ApplicationRecord


def _normalize_text(value: str) -> str:
    return " ".join(value.strip().lower().split())


def _is_same_application(a: ApplicationRecord, b: ApplicationRecord) -> bool:
    return (
        _normalize_text(a.company) == _normalize_text(b.company)
        and _normalize_text(a.role) == _normalize_text(b.role)
    )


def load_application_records() -> list[ApplicationRecord]:
    path = settings.applications_path

    if not path.exists():
        return []

    with open(path, "r", encoding="utf-8") as f:
        raw_text = f.read().strip()

    if not raw_text:
        return []

    try:
        raw_data = json.loads(raw_text)
    except json.JSONDecodeError:
        return []

    if not isinstance(raw_data, list):
        raise ValueError("applications.json must contain a list.")

    return [ApplicationRecord(**item) for item in raw_data]


def save_application_records(records: list[ApplicationRecord]) -> None:
    path = settings.applications_path
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(
            [record.model_dump() for record in records],
            f,
            indent=2,
            ensure_ascii=False,
        )


def find_existing_application(company: str, role: str) -> ApplicationRecord | None:
    probe = ApplicationRecord(company=company, role=role)

    for record in load_application_records():
        if _is_same_application(record, probe):
            return record

    return None


def has_existing_reminder(company: str, role: str, reminder_date: str) -> bool:
    existing = find_existing_application(company=company, role=role)
    if not existing:
        return False

    return _normalize_text(existing.reminder_date) == _normalize_text(reminder_date)


def add_application_record(record: ApplicationRecord) -> bool:
    records = load_application_records()

    for existing in records:
        if _is_same_application(existing, record):
            return False

    records.append(record)
    save_application_records(records)
    return True


def create_application_record(
    company: str,
    role: str,
    email_subject: str = "",
    email_body: str = "",
    status: str = "drafted",
    source: str = "manual",
    notes: str = "",
    reminder_date: str = "",
) -> ApplicationRecord:
    return ApplicationRecord(
        company=company,
        role=role,
        status=status,
        source=source,
        notes=notes,
        reminder_date=reminder_date,
        email_subject=email_subject,
        email_body=email_body,
        created_at=datetime.now(timezone.utc).isoformat(),
    )