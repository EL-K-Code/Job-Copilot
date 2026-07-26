from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from app.config import settings
from app.tenancy import normalize_user_id


_PASSWORD_SCHEME = "pbkdf2_sha256"
_PASSWORD_ITERATIONS = 390_000


def hash_password(password: str, *, salt: bytes | None = None) -> str:
    """Create a salted PBKDF2 password hash suitable for the private beta registry."""
    if len(password) < 10:
        raise ValueError("Private beta passwords must contain at least 10 characters.")
    effective_salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        effective_salt,
        _PASSWORD_ITERATIONS,
    )
    return (
        f"{_PASSWORD_SCHEME}${_PASSWORD_ITERATIONS}$"
        f"{effective_salt.hex()}${digest.hex()}"
    )


def verify_password(password: str, encoded_hash: str) -> bool:
    """Verify a password without exposing timing differences for valid hashes."""
    try:
        scheme, raw_iterations, raw_salt, expected_digest = encoded_hash.split("$", 3)
        if scheme != _PASSWORD_SCHEME:
            return False
        iterations = int(raw_iterations)
        salt = bytes.fromhex(raw_salt)
        actual_digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            iterations,
        ).hex()
    except (TypeError, ValueError):
        return False
    return hmac.compare_digest(actual_digest, expected_digest)


def load_beta_users(path: Path | None = None) -> dict[str, dict[str, Any]]:
    """Load the private beta user registry keyed by normalized user ID."""
    target = path or settings.beta_users_path
    if not target.exists():
        return {}

    raw_text = target.read_text(encoding="utf-8").strip()
    if not raw_text:
        return {}

    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Private beta user registry is not valid JSON: {target}") from exc

    if not isinstance(payload, list):
        raise ValueError("Private beta user registry must contain a list.")

    users: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(payload, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Beta user entry {index} must be a JSON object.")
        user_id = normalize_user_id(str(item.get("user_id", "")))
        password_hash = str(item.get("password_hash", "")).strip()
        if not password_hash:
            raise ValueError(f"Beta user {user_id} has no password_hash.")
        if user_id in users:
            raise ValueError(f"Duplicate beta user ID: {user_id}")
        users[user_id] = {
            "user_id": user_id,
            "display_name": str(item.get("display_name", user_id)).strip() or user_id,
            "password_hash": password_hash,
            "enabled": bool(item.get("enabled", True)),
        }
    return users


def authenticate_beta_user(
    user_id: str,
    password: str,
    *,
    path: Path | None = None,
) -> dict[str, Any] | None:
    """Return a safe public user record only when credentials are valid and enabled."""
    normalized = normalize_user_id(user_id)
    user = load_beta_users(path).get(normalized)
    if not user or not user["enabled"]:
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    return {
        "user_id": user["user_id"],
        "display_name": user["display_name"],
    }


def _atomic_write_registry(path: Path, payload: list[dict[str, Any]]) -> None:
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
            json.dump(payload, temporary_file, indent=2, ensure_ascii=False)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
            temporary_path = Path(temporary_file.name)
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink(missing_ok=True)


def upsert_beta_user(
    user_id: str,
    password: str,
    *,
    display_name: str = "",
    enabled: bool = True,
    path: Path | None = None,
) -> dict[str, Any]:
    """Create or rotate one private beta account without storing a plaintext password."""
    target = path or settings.beta_users_path
    normalized = normalize_user_id(user_id)
    existing = load_beta_users(target)
    existing[normalized] = {
        "user_id": normalized,
        "display_name": display_name.strip() or normalized,
        "password_hash": hash_password(password),
        "enabled": enabled,
    }
    payload = [existing[key] for key in sorted(existing)]
    _atomic_write_registry(target, payload)
    return {
        "user_id": normalized,
        "display_name": existing[normalized]["display_name"],
        "enabled": enabled,
    }
