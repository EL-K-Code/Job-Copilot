from __future__ import annotations

from types import SimpleNamespace

from app.services import applications_store, persistence
from app.schemas import ApplicationRecord


class _FakeResponse:
    def __init__(self, payload=None, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


def _configure(monkeypatch, *, key: str = "sb_secret_server-key"):
    monkeypatch.setattr(
        persistence,
        "settings",
        SimpleNamespace(
            persistence_backend="supabase",
            supabase_url="https://example.supabase.co",
            supabase_secret_key=key,
            supabase_timeout_seconds=7,
        ),
    )


def test_current_supabase_secret_key_is_apikey_only_and_never_in_payload(monkeypatch):
    _configure(monkeypatch)
    calls = []

    def fake_request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        return _FakeResponse(None, 201)

    monkeypatch.setattr(persistence.requests, "request", fake_request)
    persistence.save_state("alice", "profile_memories", [{"id": "m1"}])

    method, url, kwargs = calls[0]
    assert method == "POST"
    assert url.endswith("/rest/v1/jobcopilot_state")
    assert kwargs["json"] == {
        "user_id": "alice",
        "namespace": "profile_memories",
        "payload": [{"id": "m1"}],
    }
    assert kwargs["headers"]["apikey"] == "sb_secret_server-key"
    assert "Authorization" not in kwargs["headers"]
    assert "sb_secret_server-key" not in str(kwargs["json"])


def test_legacy_service_role_jwt_keeps_bearer_header(monkeypatch):
    _configure(monkeypatch, key="legacy.jwt.service-role")
    headers = persistence._headers()
    assert headers["apikey"] == "legacy.jwt.service-role"
    assert headers["Authorization"] == "Bearer legacy.jwt.service-role"


def test_load_state_returns_tenant_scoped_payload(monkeypatch):
    _configure(monkeypatch)
    captured = {}

    def fake_request(method, url, **kwargs):
        captured.update(kwargs)
        return _FakeResponse([{"payload": [{"id": "alice_fact"}]}])

    monkeypatch.setattr(persistence.requests, "request", fake_request)
    payload = persistence.load_state("alice", "profile_memories", [])

    assert payload == [{"id": "alice_fact"}]
    assert captured["params"]["user_id"] == "eq.alice"
    assert captured["params"]["namespace"] == "eq.profile_memories"


def test_application_store_uses_durable_backend_for_authenticated_user(monkeypatch):
    stored = []
    monkeypatch.setattr(applications_store, "using_supabase", lambda: True)
    monkeypatch.setattr(
        applications_store,
        "load_state",
        lambda user_id, namespace, default: list(stored),
    )

    def fake_save(user_id, namespace, payload):
        stored[:] = payload

    monkeypatch.setattr(applications_store, "save_state", fake_save)

    record = ApplicationRecord(company="Example AI", role="ML Engineer")
    assert applications_store.add_application_record(record, user_id="alice") is True
    assert applications_store.load_application_records("alice")[0].company == "Example AI"
    assert applications_store.add_application_record(record, user_id="alice") is False


def test_auto_backend_falls_back_to_local_without_secrets(monkeypatch):
    monkeypatch.setattr(
        persistence,
        "settings",
        SimpleNamespace(
            persistence_backend="auto",
            supabase_url="",
            supabase_secret_key="",
        ),
    )
    assert persistence.using_supabase() is False
