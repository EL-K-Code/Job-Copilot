from __future__ import annotations

from types import SimpleNamespace

from app.deployment_readiness import hosted_recruiter_demo_issues


def _settings(**overrides):
    values = {
        "hosted_recruiter_demo": True,
        "persistence_backend": "supabase",
        "supabase_url": "https://example.supabase.co",
        "supabase_secret_key": "sb_secret_test",
        "beta_auth_enabled": True,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_hosted_demo_accepts_safe_configuration():
    assert hosted_recruiter_demo_issues(_settings()) == []


def test_hosted_demo_requires_explicit_supabase_backend():
    issues = hosted_recruiter_demo_issues(
        _settings(persistence_backend="auto")
    )
    assert "PERSISTENCE_BACKEND must be set to 'supabase'." in issues


def test_hosted_demo_requires_supabase_credentials_and_auth():
    issues = hosted_recruiter_demo_issues(
        _settings(
            supabase_url="",
            supabase_secret_key="",
            beta_auth_enabled=False,
        )
    )

    assert "SUPABASE_URL is required." in issues
    assert "SUPABASE_SECRET_KEY is required." in issues
    assert "BETA_AUTH_ENABLED must be true." in issues


def test_local_mode_does_not_require_hosted_infrastructure():
    settings = _settings(
        hosted_recruiter_demo=False,
        persistence_backend="auto",
        supabase_url="",
        supabase_secret_key="",
        beta_auth_enabled=False,
    )

    assert hosted_recruiter_demo_issues(settings) == []
