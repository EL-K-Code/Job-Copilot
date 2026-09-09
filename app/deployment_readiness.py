from __future__ import annotations

from typing import Protocol


class HostedSettings(Protocol):
    hosted_recruiter_demo: bool
    persistence_backend: str
    supabase_url: str
    supabase_secret_key: str
    beta_auth_enabled: bool


def hosted_recruiter_demo_issues(settings: HostedSettings) -> list[str]:
    """Return actionable configuration errors for the hosted recruiter demo."""
    if not settings.hosted_recruiter_demo:
        return []

    issues: list[str] = []
    if settings.persistence_backend.strip().lower() != "supabase":
        issues.append("PERSISTENCE_BACKEND must be set to 'supabase'.")
    if not settings.supabase_url.strip():
        issues.append("SUPABASE_URL is required.")
    if not settings.supabase_secret_key.strip():
        issues.append("SUPABASE_SECRET_KEY is required.")
    if not settings.beta_auth_enabled:
        issues.append("BETA_AUTH_ENABLED must be true.")
    return issues
