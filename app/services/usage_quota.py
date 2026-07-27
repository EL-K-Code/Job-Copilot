from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import Lock
from typing import Any

from app.config import settings
from app.tenancy import ensure_user_directories


_USAGE_LOCK = Lock()


class UsageQuotaExceeded(RuntimeError):
    """Raised before a paid AI operation when the user's daily quota is exhausted."""


@dataclass(frozen=True)
class UsageSnapshot:
    user_id: str
    day: str
    used: int
    limit: int
    remaining: int
    operations: dict[str, int]

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


def _empty_payload(day: str) -> dict[str, Any]:
    return {"day": day, "used": 0, "operations": {}}


def _load_payload(path: Path, day: str) -> dict[str, Any]:
    if not path.exists():
        return _empty_payload(day)

    raw_text = path.read_text(encoding="utf-8").strip()
    if not raw_text:
        return _empty_payload(day)

    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Usage ledger is not valid JSON: {path}") from exc

    if not isinstance(payload, dict):
        raise ValueError("Usage ledger must contain a JSON object.")
    if str(payload.get("day", "")) != day:
        return _empty_payload(day)

    used = payload.get("used", 0)
    operations = payload.get("operations", {})
    if not isinstance(used, int) or used < 0:
        raise ValueError("Usage ledger field 'used' must be a non-negative integer.")
    if not isinstance(operations, dict) or any(
        not isinstance(key, str) or not isinstance(value, int) or value < 0
        for key, value in operations.items()
    ):
        raise ValueError("Usage ledger operations must map names to non-negative integers.")

    return {"day": day, "used": used, "operations": dict(operations)}


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
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


def get_daily_usage(
    user_id: str,
    *,
    day: date | None = None,
    limit: int | None = None,
) -> UsageSnapshot:
    """Return today's usage without consuming quota."""
    effective_day = (day or date.today()).isoformat()
    effective_limit = settings.beta_daily_ai_limit if limit is None else limit
    if effective_limit < 1:
        raise ValueError("Daily AI limit must be at least 1.")

    paths = ensure_user_directories(user_id)
    with _USAGE_LOCK:
        payload = _load_payload(paths.usage, effective_day)

    used = int(payload["used"])
    return UsageSnapshot(
        user_id=paths.user_id,
        day=effective_day,
        used=used,
        limit=effective_limit,
        remaining=max(effective_limit - used, 0),
        operations=dict(payload["operations"]),
    )


def consume_ai_operation(
    user_id: str,
    operation: str,
    *,
    day: date | None = None,
    limit: int | None = None,
) -> UsageSnapshot:
    """Atomically reserve one paid AI operation before the provider call starts.

    A started operation counts even if the downstream provider later fails. This keeps the
    quota conservative and prevents repeated failing retries from creating unbounded cost.
    """
    normalized_operation = "_".join(str(operation).strip().casefold().split())
    if not normalized_operation:
        raise ValueError("Usage operation name cannot be empty.")

    effective_day = (day or date.today()).isoformat()
    effective_limit = settings.beta_daily_ai_limit if limit is None else limit
    if effective_limit < 1:
        raise ValueError("Daily AI limit must be at least 1.")

    paths = ensure_user_directories(user_id)
    with _USAGE_LOCK:
        payload = _load_payload(paths.usage, effective_day)
        used = int(payload["used"])
        if used >= effective_limit:
            raise UsageQuotaExceeded(
                f"Daily AI quota reached ({used}/{effective_limit}). Try again tomorrow."
            )

        operations = dict(payload["operations"])
        operations[normalized_operation] = operations.get(normalized_operation, 0) + 1
        used += 1
        updated = {
            "day": effective_day,
            "used": used,
            "operations": operations,
        }
        _atomic_write(paths.usage, updated)

    return UsageSnapshot(
        user_id=paths.user_id,
        day=effective_day,
        used=used,
        limit=effective_limit,
        remaining=max(effective_limit - used, 0),
        operations=operations,
    )
