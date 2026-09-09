from __future__ import annotations

from typing import Protocol
from urllib.parse import urlparse


class HostedSettings(Protocol):
    hosted_recruiter_demo: bool
    hosted_google_oauth_enabled: bool
    persistence_backend: str
    supabase_url: str
    supabase_secret_key: str
    beta_auth_enabled: bool
    google_oauth_client_id: str
    google_oauth_client_secret: str
    google_oauth_redirect_uri: str
    google_token_encryption_key: str


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

    if getattr(settings, "hosted_google_oauth_enabled", False):
        if not settings.google_oauth_client_id.strip():
            issues.append("GOOGLE_OAUTH_CLIENT_ID is required when hosted Google OAuth is enabled.")
        if not settings.google_oauth_client_secret.strip():
            issues.append("GOOGLE_OAUTH_CLIENT_SECRET is required when hosted Google OAuth is enabled.")
        if not settings.google_oauth_redirect_uri.strip():
            issues.append("GOOGLE_OAUTH_REDIRECT_URI is required when hosted Google OAuth is enabled.")
        else:
            parsed = urlparse(settings.google_oauth_redirect_uri)
            if parsed.scheme != "https" or not parsed.netloc:
                issues.append("GOOGLE_OAUTH_REDIRECT_URI must be an absolute HTTPS URL.")
        if len(settings.google_token_encryption_key.strip()) < 32:
            issues.append("GOOGLE_TOKEN_ENCRYPTION_KEY must contain at least 32 characters.")
    return issues
