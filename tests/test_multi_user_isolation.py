from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from langchain_core.documents import Document

from app import auth, tenancy
from app.graph import retrieve_memory_node
from app.schemas import ApplicationRecord
from app.services import applications_store
from app.services.profile_store import export_user_data, save_user_profile_memories


def _user_paths(root: Path, user_id: str):
    user_root = root / user_id
    return SimpleNamespace(
        user_id=user_id,
        root=user_root,
        profile_memories=user_root / "profile_memories.json",
        memory_index=user_root / "faiss_index",
        applications=user_root / "applications.json",
        google_token=user_root / "google_token.json",
        uploads=user_root / "uploads",
    )


def test_user_ids_reject_path_traversal():
    for unsafe in ("../alice", "Alice/../../bob", "a", "alice.bob", "alice bob"):
        with pytest.raises(ValueError):
            tenancy.normalize_user_id(unsafe)


def test_user_paths_are_siblings_under_private_root(monkeypatch, tmp_path):
    monkeypatch.setattr(
        tenancy,
        "settings",
        SimpleNamespace(user_data_root_path=tmp_path / "users"),
    )

    alice = tenancy.get_user_paths("alice")
    bob = tenancy.get_user_paths("bob")

    assert alice.root.parent == bob.root.parent == (tmp_path / "users").resolve()
    assert alice.applications != bob.applications
    assert alice.profile_memories != bob.profile_memories
    assert alice.google_token != bob.google_token


def test_application_records_never_cross_user_boundaries(monkeypatch, tmp_path):
    monkeypatch.setattr(
        applications_store,
        "get_user_paths",
        lambda user_id: _user_paths(tmp_path, user_id),
    )

    alice_record = ApplicationRecord(company="Alice Labs", role="ML Engineer")
    bob_record = ApplicationRecord(company="Bob Systems", role="Data Engineer")

    assert applications_store.add_application_record(alice_record, user_id="alice")
    assert applications_store.add_application_record(bob_record, user_id="bob")

    alice_records = applications_store.load_application_records(user_id="alice")
    bob_records = applications_store.load_application_records(user_id="bob")

    assert [record.company for record in alice_records] == ["Alice Labs"]
    assert [record.company for record in bob_records] == ["Bob Systems"]
    assert applications_store.find_existing_application(
        "Bob Systems", "Data Engineer", user_id="alice"
    ) is None


def test_pipeline_retrieval_forwards_authenticated_user(monkeypatch):
    captured = {}

    def fake_retrieve(query, k, *, user_id=None):
        captured.update(query=query, k=k, user_id=user_id)
        return [
            Document(
                page_content="Alice works with Python.",
                metadata={"id": "alice_python", "type": "skill"},
            )
        ]

    monkeypatch.setattr("app.graph.retrieve_profile_context", fake_retrieve)

    result = retrieve_memory_node(
        {
            "user_id": "alice",
            "retrieval_query": "Python machine learning",
        }
    )

    assert captured == {
        "query": "Python machine learning",
        "k": 8,
        "user_id": "alice",
    }
    assert result["retrieved_memory_records"][0]["id"] == "alice_python"


def test_beta_password_registry_never_stores_plaintext(tmp_path):
    registry = tmp_path / "beta_users.json"
    user = auth.upsert_beta_user(
        "alice",
        "a-strong-private-password",
        display_name="Alice",
        path=registry,
    )

    raw_text = registry.read_text(encoding="utf-8")
    assert "a-strong-private-password" not in raw_text
    assert "pbkdf2_sha256" in raw_text
    assert auth.authenticate_beta_user(
        "alice",
        "a-strong-private-password",
        path=registry,
    ) == {"user_id": "alice", "display_name": "Alice"}
    assert auth.authenticate_beta_user("alice", "wrong-password", path=registry) is None
    assert user["enabled"] is True


def test_profile_export_contains_only_requested_user(monkeypatch, tmp_path):
    import app.services.profile_store as profile_store

    monkeypatch.setattr(
        profile_store,
        "ensure_user_directories",
        lambda user_id: _user_paths(tmp_path, user_id),
    )
    monkeypatch.setattr(
        profile_store,
        "get_user_paths",
        lambda user_id: _user_paths(tmp_path, user_id),
    )

    alice_memories = [
        {"id": "alice_python", "type": "skill", "content": "Alice uses Python."}
    ]
    bob_paths = _user_paths(tmp_path, "bob")
    bob_paths.root.mkdir(parents=True, exist_ok=True)
    bob_paths.profile_memories.write_text(
        json.dumps(
            [{"id": "bob_sql", "type": "skill", "content": "Bob uses SQL."}]
        ),
        encoding="utf-8",
    )

    save_user_profile_memories("alice", alice_memories)
    exported = export_user_data("alice")

    with zipfile.ZipFile(io.BytesIO(exported)) as archive:
        contents = "\n".join(
            archive.read(name).decode("utf-8") for name in archive.namelist()
        )

    assert "Alice uses Python" in contents
    assert "Bob uses SQL" not in contents
