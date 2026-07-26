from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.schemas import ApplicationRecord
from app.services import applications_store


def _paths(root, user_id):
    user_root = root / user_id
    return SimpleNamespace(applications=user_root / "applications.json")


def test_update_application_record_changes_only_requested_tenant(monkeypatch, tmp_path):
    monkeypatch.setattr(
        applications_store,
        "get_user_paths",
        lambda user_id: _paths(tmp_path, user_id),
    )

    applications_store.add_application_record(
        ApplicationRecord(company="Alice Labs", role="ML Engineer"),
        user_id="alice",
    )
    applications_store.add_application_record(
        ApplicationRecord(company="Bob Systems", role="Data Engineer"),
        user_id="bob",
    )

    updated = applications_store.update_application_record(
        "Alice Labs",
        "ML Engineer",
        user_id="alice",
        status="interview",
        reminder_date="2026-08-03",
        notes="Technical interview confirmed",
    )

    assert updated is not None
    assert updated.status == "interview"
    assert updated.reminder_date == "2026-08-03"
    assert applications_store.load_application_records(user_id="bob")[0].status == "drafted"


def test_update_application_record_validates_status_before_saving(monkeypatch, tmp_path):
    monkeypatch.setattr(
        applications_store,
        "get_user_paths",
        lambda user_id: _paths(tmp_path, user_id),
    )
    applications_store.add_application_record(
        ApplicationRecord(company="Example", role="Engineer"),
        user_id="alice",
    )

    with pytest.raises(ValueError):
        applications_store.update_application_record(
            "Example",
            "Engineer",
            user_id="alice",
            status="invalid-status",
        )

    assert applications_store.load_application_records(user_id="alice")[0].status == "drafted"
