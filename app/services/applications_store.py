from __future__ import annotations

import json
from datetime import datetime, timezone

from app.config import settings
from app.schemas import ApplicationRecord


def load_application_records() -> list[ApplicationRecord]:
    path = settings.applications_path

    if not path.exists():
        return []

    with open(path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

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


def add_application_record(record: ApplicationRecord) -> None:
    records = load_application_records()
    records.append(record)
    save_application_records(records)


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