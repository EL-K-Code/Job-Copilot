from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile

from app.config import settings
from app.schemas import ApplicationRecord
from app.tenancy import get_user_paths


def _normalize_text(value: str) -> str:
    return " ".join(value.strip().lower().split())


def _is_same_application(a: ApplicationRecord, b: ApplicationRecord) -> bool:
    return (
        _normalize_text(a.company) == _normalize_text(b.company)
        and _normalize_text(a.role) == _normalize_text(b.role)
    )


def _applications_path(user_id: str | None = None) -> Path:
    return settings.applications_path if user_id is None else get_user_paths(user_id).applications


def load_application_records(user_id: str | None = None) -> list[ApplicationRecord]:
    path = _applications_path(user_id)

    if not path.exists():
        return []

    raw_text = path.read_text(encoding="utf-8").strip()
    if not raw_text:
        return []

    try:
        raw_data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Application store is not valid JSON: {path}. "
            "The file was left untouched so it can be inspected or restored."
        ) from exc

    if not isinstance(raw_data, list):
        raise ValueError("applications.json must contain a list.")

    return [ApplicationRecord(**item) for item in raw_data]


def _atomic_json_write(path: Path, payload: list[dict]) -> None:
    """Write JSON through a temporary file and atomically replace the target."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None

    try:
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            json.dump(
                payload,
                temporary_file,
                indent=2,
                ensure_ascii=False,
            )
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
            temporary_path = Path(temporary_file.name)

        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink(missing_ok=True)


def save_application_records(
    records: list[ApplicationRecord],
    user_id: str | None = None,
) -> None:
    _atomic_json_write(
        _applications_path(user_id),
        [record.model_dump() for record in records],
    )


def find_existing_application(
    company: str,
    role: str,
    user_id: str | None = None,
) -> ApplicationRecord | None:
    probe = ApplicationRecord(company=company, role=role)

    for record in load_application_records(user_id=user_id):
        if _is_same_application(record, probe):
            return record

    return None


def has_existing_reminder(
    company: str,
    role: str,
    reminder_date: str,
    user_id: str | None = None,
) -> bool:
    existing = find_existing_application(
        company=company,
        role=role,
        user_id=user_id,
    )
    if not existing:
        return False

    return _normalize_text(existing.reminder_date) == _normalize_text(reminder_date)


def add_application_record(
    record: ApplicationRecord,
    user_id: str | None = None,
) -> bool:
    records = load_application_records(user_id=user_id)

    for existing in records:
        if _is_same_application(existing, record):
            return False

    records.append(record)
    save_application_records(records, user_id=user_id)
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
