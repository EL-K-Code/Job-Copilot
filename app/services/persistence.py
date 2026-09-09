from __future__ import annotations

from copy import deepcopy
from typing import Any

import requests

from app.config import settings


class PersistenceConfigurationError(RuntimeError):
    """Raised when Supabase persistence is requested without complete credentials."""


class PersistenceBackendError(RuntimeError):
    """Raised when the configured persistent backend cannot complete an operation."""


def using_supabase() -> bool:
    """Return whether tenant state should be stored in Supabase."""
    backend = settings.persistence_backend.strip().casefold()
    if backend not in {"auto", "local", "supabase"}:
        raise PersistenceConfigurationError(
            "PERSISTENCE_BACKEND must be one of: auto, local, supabase."
        )
    if backend == "local":
        return False

    configured = bool(
        settings.supabase_url.strip() and settings.supabase_service_role_key.strip()
    )
    if backend == "supabase" and not configured:
        raise PersistenceConfigurationError(
            "Supabase persistence requires SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY."
        )
    return configured


def _base_url() -> str:
    return settings.supabase_url.rstrip("/")


def _headers(*, prefer: str | None = None) -> dict[str, str]:
    key = settings.supabase_service_role_key.strip()
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    if prefer:
        headers["Prefer"] = prefer
    return headers


def _request(
    method: str,
    path: str,
    *,
    params: dict[str, str] | None = None,
    json_payload: Any | None = None,
    prefer: str | None = None,
) -> requests.Response:
    try:
        response = requests.request(
            method,
            f"{_base_url()}{path}",
            headers=_headers(prefer=prefer),
            params=params,
            json=json_payload,
            timeout=settings.supabase_timeout_seconds,
        )
    except requests.RequestException as exc:
        raise PersistenceBackendError(
            "The persistent data store could not be reached."
        ) from exc

    if response.status_code >= 400:
        detail = ""
        try:
            payload = response.json()
            detail = str(payload.get("message") or payload.get("hint") or "").strip()
        except Exception:
            detail = ""
        suffix = f" ({detail})" if detail else ""
        raise PersistenceBackendError(
            f"Persistent data store request failed with HTTP {response.status_code}{suffix}."
        )
    return response


def load_state(user_id: str, namespace: str, default: Any) -> Any:
    """Load one tenant-scoped JSON payload from Supabase or return a copy of default."""
    if not using_supabase():
        return deepcopy(default)
    response = _request(
        "GET",
        "/rest/v1/jobcopilot_state",
        params={
            "select": "payload",
            "user_id": f"eq.{user_id}",
            "namespace": f"eq.{namespace}",
            "limit": "1",
        },
    )
    rows = response.json()
    if not rows:
        return deepcopy(default)
    return rows[0].get("payload", deepcopy(default))


def save_state(user_id: str, namespace: str, payload: Any) -> None:
    """Upsert one tenant-scoped JSON payload in Supabase."""
    if not using_supabase():
        raise PersistenceConfigurationError(
            "save_state is only available when Supabase persistence is enabled."
        )
    _request(
        "POST",
        "/rest/v1/jobcopilot_state",
        params={"on_conflict": "user_id,namespace"},
        json_payload={
            "user_id": user_id,
            "namespace": namespace,
            "payload": payload,
        },
        prefer="resolution=merge-duplicates,return=minimal",
    )


def list_namespace(namespace: str) -> list[dict[str, Any]]:
    """Return all server-side rows for one namespace, used only by private-beta auth."""
    if not using_supabase():
        return []
    response = _request(
        "GET",
        "/rest/v1/jobcopilot_state",
        params={
            "select": "user_id,payload",
            "namespace": f"eq.{namespace}",
            "order": "user_id.asc",
        },
    )
    rows = response.json()
    return rows if isinstance(rows, list) else []


def delete_user_state(user_id: str) -> None:
    if not using_supabase():
        return
    _request(
        "DELETE",
        "/rest/v1/jobcopilot_state",
        params={"user_id": f"eq.{user_id}"},
        prefer="return=minimal",
    )
    _request(
        "DELETE",
        "/rest/v1/jobcopilot_usage",
        params={"user_id": f"eq.{user_id}"},
        prefer="return=minimal",
    )


def load_usage(user_id: str, day: str) -> dict[str, Any]:
    if not using_supabase():
        return {"day": day, "used": 0, "operations": {}}
    response = _request(
        "GET",
        "/rest/v1/jobcopilot_usage",
        params={
            "select": "day,used,operations",
            "user_id": f"eq.{user_id}",
            "day": f"eq.{day}",
            "limit": "1",
        },
    )
    rows = response.json()
    if not rows:
        return {"day": day, "used": 0, "operations": {}}
    row = rows[0]
    return {
        "day": str(row.get("day", day)),
        "used": int(row.get("used", 0)),
        "operations": dict(row.get("operations") or {}),
    }


def consume_usage(
    user_id: str,
    day: str,
    operation: str,
    limit: int,
) -> dict[str, Any]:
    """Atomically reserve one quota unit through a Postgres RPC function."""
    if not using_supabase():
        raise PersistenceConfigurationError(
            "consume_usage is only available when Supabase persistence is enabled."
        )
    try:
        response = _request(
            "POST",
            "/rest/v1/rpc/jobcopilot_consume_quota",
            json_payload={
                "p_user_id": user_id,
                "p_day": day,
                "p_operation": operation,
                "p_limit": limit,
            },
        )
    except PersistenceBackendError as exc:
        if "quota_exceeded" in str(exc).casefold():
            raise
        raise

    payload = response.json()
    if isinstance(payload, list) and payload:
        payload = payload[0]
    if not isinstance(payload, dict):
        raise PersistenceBackendError("Quota RPC returned an invalid response.")
    return payload
