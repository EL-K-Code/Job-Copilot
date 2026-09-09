from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from google.oauth2.credentials import Credentials

from app import agent_graph, agent_tools
from app.deployment_readiness import hosted_recruiter_demo_issues
from app.services import google_oauth


def _oauth_settings(**overrides):
    values = {
        "hosted_recruiter_demo": True,
        "hosted_google_oauth_enabled": True,
        "persistence_backend": "supabase",
        "supabase_url": "https://example.supabase.co",
        "supabase_secret_key": "sb_secret_test",
        "beta_auth_enabled": True,
        "google_oauth_client_id": "client-id.apps.googleusercontent.com",
        "google_oauth_client_secret": "client-secret",
        "google_oauth_redirect_uri": "https://jobcopilot.example.app/",
        "google_token_encryption_key": "x" * 48,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _configure_oauth(monkeypatch):
    storage = {}
    deleted = []
    monkeypatch.setattr(google_oauth, "settings", _oauth_settings())
    monkeypatch.setattr(google_oauth, "using_supabase", lambda: True)
    monkeypatch.setattr(
        google_oauth,
        "save_state",
        lambda user_id, namespace, payload: storage.__setitem__((user_id, namespace), payload),
    )
    monkeypatch.setattr(
        google_oauth,
        "load_state",
        lambda user_id, namespace, default: storage.get((user_id, namespace), default),
    )
    monkeypatch.setattr(
        google_oauth,
        "delete_state",
        lambda user_id, namespace: deleted.append((user_id, namespace)),
    )
    return storage, deleted


def test_signed_oauth_state_is_user_bound_and_expires(monkeypatch):
    _configure_oauth(monkeypatch)
    state = google_oauth.create_signed_oauth_state("recruiter-demo", now=1_000)

    assert google_oauth.verify_signed_oauth_state(state, now=1_100) == "recruiter-demo"

    with pytest.raises(google_oauth.GoogleOAuthStateError, match="expired"):
        google_oauth.verify_signed_oauth_state(state, now=1_700)


def test_signed_oauth_state_rejects_tampering(monkeypatch):
    _configure_oauth(monkeypatch)
    state = google_oauth.create_signed_oauth_state("recruiter-demo", now=1_000)
    encoded, signature = state.split(".", 1)
    tampered = f"{encoded[:-1]}A.{signature}"

    with pytest.raises(google_oauth.GoogleOAuthStateError):
        google_oauth.verify_signed_oauth_state(tampered, now=1_050)


def test_google_credentials_are_encrypted_before_persistence(monkeypatch):
    storage, _ = _configure_oauth(monkeypatch)
    credentials = Credentials(
        token="access-token-secret",
        refresh_token="refresh-token-secret",
        token_uri="https://oauth2.googleapis.com/token",
        client_id="client-id.apps.googleusercontent.com",
        client_secret="client-secret",
        scopes=google_oauth.GOOGLE_SCOPES,
        expiry=datetime.utcnow() + timedelta(hours=1),
    )

    google_oauth.save_hosted_google_credentials("recruiter-demo", credentials)
    stored = storage[("recruiter-demo", "google_oauth")]
    serialized = str(stored)

    assert "refresh-token-secret" not in serialized
    assert "access-token-secret" not in serialized
    assert stored["ciphertext"]

    restored = google_oauth.load_hosted_google_credentials("recruiter-demo")
    assert restored is not None
    assert restored.refresh_token == "refresh-token-secret"
    assert restored.token == "access-token-secret"


def test_disconnect_removes_only_google_namespace(monkeypatch):
    _, deleted = _configure_oauth(monkeypatch)
    google_oauth.disconnect_hosted_google("recruiter-demo")
    assert deleted == [("recruiter-demo", "google_oauth")]


def test_hosted_oauth_enables_google_agent_tools(monkeypatch):
    monkeypatch.setattr(
        agent_tools,
        "settings",
        SimpleNamespace(hosted_recruiter_demo=True, hosted_google_oauth_enabled=True),
    )
    names = {tool.name for tool in agent_tools.build_agent_tools("recruiter-demo")}
    assert "create_gmail_draft_tool" in names
    assert "create_followup_reminder_tool" in names


def test_hosted_oauth_prompt_keeps_confirmation_rules(monkeypatch):
    monkeypatch.setattr(
        agent_graph,
        "settings",
        SimpleNamespace(hosted_recruiter_demo=True, hosted_google_oauth_enabled=True),
    )
    prompt = agent_graph._system_prompt()
    assert "Never create a Gmail draft or Calendar event without explicit confirmation" in prompt
    assert "must connect it from Settings" in prompt


def test_hosted_oauth_configuration_is_fail_closed():
    issues = hosted_recruiter_demo_issues(
        _oauth_settings(
            google_oauth_client_id="",
            google_oauth_client_secret="",
            google_oauth_redirect_uri="http://localhost:8501",
            google_token_encryption_key="short",
        )
    )

    assert any("GOOGLE_OAUTH_CLIENT_ID" in issue for issue in issues)
    assert any("GOOGLE_OAUTH_CLIENT_SECRET" in issue for issue in issues)
    assert "GOOGLE_OAUTH_REDIRECT_URI must be an absolute HTTPS URL." in issues
    assert "GOOGLE_TOKEN_ENCRYPTION_KEY must contain at least 32 characters." in issues
