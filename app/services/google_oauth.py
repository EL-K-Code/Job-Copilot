from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from datetime import datetime, timezone
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow

from app.config import settings
from app.services.persistence import delete_state, load_state, save_state, using_supabase
from app.tenancy import normalize_user_id


GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/calendar.events",
]
_GOOGLE_NAMESPACE = "google_oauth"
_STATE_MAX_AGE_SECONDS = 10 * 60
_TOKEN_URI = "https://oauth2.googleapis.com/token"
_AUTH_URI = "https://accounts.google.com/o/oauth2/auth"


class GoogleOAuthConfigurationError(RuntimeError):
    """Raised when hosted Google OAuth is enabled without all required secrets."""


class GoogleOAuthStateError(RuntimeError):
    """Raised when an OAuth callback state token is invalid or expired."""


def hosted_google_oauth_configured() -> bool:
    """Return whether the hosted OAuth feature has every required server secret."""
    return bool(
        settings.hosted_google_oauth_enabled
        and settings.google_oauth_client_id.strip()
        and settings.google_oauth_client_secret.strip()
        and settings.google_oauth_redirect_uri.strip()
        and settings.google_token_encryption_key.strip()
    )


def _require_hosted_configuration() -> None:
    if not settings.hosted_google_oauth_enabled:
        raise GoogleOAuthConfigurationError("Hosted Google OAuth is disabled.")
    if not using_supabase():
        raise GoogleOAuthConfigurationError(
            "Hosted Google OAuth requires Supabase persistence."
        )

    missing = []
    if not settings.google_oauth_client_id.strip():
        missing.append("GOOGLE_OAUTH_CLIENT_ID")
    if not settings.google_oauth_client_secret.strip():
        missing.append("GOOGLE_OAUTH_CLIENT_SECRET")
    if not settings.google_oauth_redirect_uri.strip():
        missing.append("GOOGLE_OAUTH_REDIRECT_URI")
    if not settings.google_token_encryption_key.strip():
        missing.append("GOOGLE_TOKEN_ENCRYPTION_KEY")
    if missing:
        raise GoogleOAuthConfigurationError(
            "Hosted Google OAuth is missing: " + ", ".join(missing)
        )


def _fernet() -> Fernet:
    _require_hosted_configuration()
    digest = hashlib.sha256(settings.google_token_encryption_key.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _client_config() -> dict[str, Any]:
    _require_hosted_configuration()
    return {
        "web": {
            "client_id": settings.google_oauth_client_id,
            "client_secret": settings.google_oauth_client_secret,
            "auth_uri": _AUTH_URI,
            "token_uri": _TOKEN_URI,
            "redirect_uris": [settings.google_oauth_redirect_uri],
        }
    }


def _base64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _base64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def create_signed_oauth_state(user_id: str, *, now: int | None = None) -> str:
    """Create a short-lived signed state token that binds the callback to one beta user."""
    _require_hosted_configuration()
    normalized = normalize_user_id(user_id)
    issued_at = int(time.time() if now is None else now)
    payload = {
        "v": 1,
        "user_id": normalized,
        "iat": issued_at,
        "nonce": secrets.token_urlsafe(18),
    }
    encoded = _base64url_encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    signature = hmac.new(
        settings.google_token_encryption_key.encode("utf-8"),
        encoded.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"{encoded}.{_base64url_encode(signature)}"


def verify_signed_oauth_state(state: str, *, now: int | None = None) -> str:
    """Validate state integrity and expiry, then return the bound normalized user ID."""
    _require_hosted_configuration()
    try:
        encoded, raw_signature = state.split(".", 1)
        expected = hmac.new(
            settings.google_token_encryption_key.encode("utf-8"),
            encoded.encode("ascii"),
            hashlib.sha256,
        ).digest()
        actual = _base64url_decode(raw_signature)
        if not hmac.compare_digest(actual, expected):
            raise GoogleOAuthStateError("Invalid Google OAuth state signature.")

        payload = json.loads(_base64url_decode(encoded).decode("utf-8"))
        if int(payload.get("v", 0)) != 1:
            raise GoogleOAuthStateError("Unsupported Google OAuth state version.")
        user_id = normalize_user_id(str(payload.get("user_id", "")))
        issued_at = int(payload.get("iat", 0))
    except GoogleOAuthStateError:
        raise
    except Exception as exc:
        raise GoogleOAuthStateError("Invalid Google OAuth state.") from exc

    current = int(time.time() if now is None else now)
    age = current - issued_at
    if age < -60 or age > _STATE_MAX_AGE_SECONDS:
        raise GoogleOAuthStateError("Google OAuth state expired. Start the connection again.")
    return user_id


def build_google_authorization_url(user_id: str) -> str:
    """Return a Google consent URL for the hosted web-server OAuth flow."""
    state = create_signed_oauth_state(user_id)
    flow = Flow.from_client_config(
        _client_config(),
        scopes=GOOGLE_SCOPES,
        state=state,
    )
    flow.redirect_uri = settings.google_oauth_redirect_uri
    authorization_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    return authorization_url


def _expiry_to_text(expiry: datetime | None) -> str:
    if expiry is None:
        return ""
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    else:
        expiry = expiry.astimezone(timezone.utc)
    return expiry.isoformat()


def _expiry_from_text(raw_expiry: str) -> datetime | None:
    if not raw_expiry:
        return None
    parsed = datetime.fromisoformat(raw_expiry)
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _credentials_payload(credentials: Credentials) -> dict[str, Any]:
    return {
        "token": credentials.token or "",
        "refresh_token": credentials.refresh_token or "",
        "expiry": _expiry_to_text(credentials.expiry),
        "scopes": list(credentials.scopes or GOOGLE_SCOPES),
    }


def _credentials_from_payload(payload: dict[str, Any]) -> Credentials:
    return Credentials(
        token=str(payload.get("token", "")) or None,
        refresh_token=str(payload.get("refresh_token", "")) or None,
        token_uri=_TOKEN_URI,
        client_id=settings.google_oauth_client_id,
        client_secret=settings.google_oauth_client_secret,
        scopes=list(payload.get("scopes") or GOOGLE_SCOPES),
        expiry=_expiry_from_text(str(payload.get("expiry", "")).strip()),
    )


def save_hosted_google_credentials(user_id: str, credentials: Credentials) -> None:
    """Encrypt and persist one user's Google OAuth credentials in server-only Supabase state."""
    normalized = normalize_user_id(user_id)
    plaintext = json.dumps(
        _credentials_payload(credentials),
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    encrypted = _fernet().encrypt(plaintext).decode("ascii")
    save_state(
        normalized,
        _GOOGLE_NAMESPACE,
        {
            "version": 1,
            "ciphertext": encrypted,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
    )


def load_hosted_google_credentials(user_id: str) -> Credentials | None:
    """Load and decrypt one user's hosted Google credentials without exposing raw tokens."""
    _require_hosted_configuration()
    normalized = normalize_user_id(user_id)
    stored = load_state(normalized, _GOOGLE_NAMESPACE, {})
    if not isinstance(stored, dict) or not stored:
        return None
    ciphertext = str(stored.get("ciphertext", "")).strip()
    if not ciphertext:
        return None
    try:
        plaintext = _fernet().decrypt(ciphertext.encode("ascii"))
        payload = json.loads(plaintext.decode("utf-8"))
    except (InvalidToken, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError("Stored Google OAuth credentials could not be decrypted.") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("Stored Google OAuth credentials are invalid.")
    return _credentials_from_payload(payload)


def get_hosted_google_credentials(user_id: str) -> Credentials:
    """Return valid hosted credentials, refreshing and re-encrypting them when needed."""
    credentials = load_hosted_google_credentials(user_id)
    if credentials is None:
        raise RuntimeError("No Google account is connected for this user.")

    if credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
        save_hosted_google_credentials(user_id, credentials)

    if not credentials.valid:
        raise RuntimeError("The Google connection is no longer valid. Reconnect Google.")
    return credentials


def hosted_google_token_exists(user_id: str) -> bool:
    """Return whether a decryptable persistent refresh token exists for the user."""
    try:
        credentials = load_hosted_google_credentials(user_id)
    except RuntimeError:
        return False
    return bool(credentials and credentials.refresh_token)


def exchange_google_oauth_callback(code: str, state: str) -> str:
    """Exchange the callback code, persist encrypted credentials, and return the bound user ID."""
    user_id = verify_signed_oauth_state(state)
    if not code.strip():
        raise RuntimeError("Google OAuth callback did not include an authorization code.")

    flow = Flow.from_client_config(
        _client_config(),
        scopes=GOOGLE_SCOPES,
        state=state,
    )
    flow.redirect_uri = settings.google_oauth_redirect_uri
    flow.fetch_token(code=code)
    credentials = flow.credentials
    if not credentials.refresh_token:
        raise RuntimeError(
            "Google did not return a refresh token. Revoke the app grant and connect again."
        )
    save_hosted_google_credentials(user_id, credentials)
    return user_id


def disconnect_hosted_google(user_id: str) -> None:
    """Remove the stored hosted Google OAuth credentials for one user."""
    delete_state(normalize_user_id(user_id), _GOOGLE_NAMESPACE)
