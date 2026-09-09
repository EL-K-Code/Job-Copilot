from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from app.config import settings


_USER_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{1,63}$")
DEFAULT_LOCAL_USER_ID = "local-demo"


@dataclass(frozen=True)
class UserPaths:
    """All private filesystem locations owned by one JobCopilot user."""

    user_id: str
    root: Path
    profile_memories: Path
    memory_index: Path
    applications: Path
    google_token: Path
    usage: Path
    uploads: Path


def normalize_user_id(user_id: str | None) -> str:
    """Validate a stable user identifier and reject path traversal or unsafe names."""
    normalized = str(user_id or DEFAULT_LOCAL_USER_ID).strip().casefold()
    if not _USER_ID_PATTERN.fullmatch(normalized):
        raise ValueError(
            "user_id must be 2-64 characters using lowercase letters, numbers, '-' or '_'."
        )
    return normalized


def get_user_paths(user_id: str | None) -> UserPaths:
    """Resolve private paths beneath USER_DATA_ROOT without allowing directory escape."""
    normalized = normalize_user_id(user_id)
    root = (settings.user_data_root_path / normalized).resolve()
    allowed_root = settings.user_data_root_path.resolve()

    if root.parent != allowed_root:
        raise ValueError("Resolved user path escaped USER_DATA_ROOT.")

    return UserPaths(
        user_id=normalized,
        root=root,
        profile_memories=root / "profile_memories.json",
        memory_index=root / "faiss_index",
        applications=root / "applications.json",
        google_token=root / "google_token.json",
        usage=root / "usage.json",
        uploads=root / "uploads",
    )


def ensure_user_directories(user_id: str | None) -> UserPaths:
    """Create disposable tenant-local directories and hydrate profile presence when needed."""
    paths = get_user_paths(user_id)
    paths.root.mkdir(parents=True, exist_ok=True)
    paths.uploads.mkdir(parents=True, exist_ok=True)

    # Some UI code checks whether the local profile mirror exists before loading it.
    # On Streamlit Cloud the filesystem is disposable, so recreate only that small
    # mirror from durable Supabase state after a restart. The source of truth remains
    # the database; FAISS indexes are intentionally rebuilt process-locally.
    from app.services.persistence import load_state, using_supabase

    if using_supabase() and not paths.profile_memories.exists():
        payload = load_state(paths.user_id, "profile_memories", [])
        if isinstance(payload, list) and payload:
            paths.profile_memories.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

    return paths
