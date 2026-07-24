from types import SimpleNamespace

import pytest

from app.schemas import ApplicationRecord
from app.services import applications_store


def _use_temporary_store(monkeypatch, tmp_path):
    store_path = tmp_path / "applications.json"
    monkeypatch.setattr(
        applications_store,
        "settings",
        SimpleNamespace(applications_path=store_path),
    )
    return store_path


def test_add_application_record_persists_and_rejects_duplicate(monkeypatch, tmp_path):
    store_path = _use_temporary_store(monkeypatch, tmp_path)
    record = ApplicationRecord(company="OpenAI", role="Applied AI Engineer")

    assert applications_store.add_application_record(record) is True
    assert store_path.exists()
    assert applications_store.add_application_record(record) is False

    loaded = applications_store.load_application_records()
    assert len(loaded) == 1
    assert loaded[0].company == "OpenAI"
    assert loaded[0].role == "Applied AI Engineer"


def test_duplicate_detection_is_case_and_whitespace_insensitive(monkeypatch, tmp_path):
    _use_temporary_store(monkeypatch, tmp_path)
    applications_store.add_application_record(
        ApplicationRecord(company="Example Labs", role="ML Engineer")
    )

    existing = applications_store.find_existing_application(
        company="  example   labs ",
        role=" ml engineer ",
    )

    assert existing is not None


def test_invalid_json_fails_without_overwriting_file(monkeypatch, tmp_path):
    store_path = _use_temporary_store(monkeypatch, tmp_path)
    store_path.write_text("{not-json", encoding="utf-8")

    with pytest.raises(ValueError, match="not valid JSON"):
        applications_store.load_application_records()

    assert store_path.read_text(encoding="utf-8") == "{not-json"
