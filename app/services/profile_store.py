from __future__ import annotations

import io
import json
import os
import shutil
import zipfile
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from app.memory import (
    clear_profile_vector_store_cache,
    load_profile_memories,
    validate_profile_memories,
)
from app.services.applications_store import load_application_records
from app.services.persistence import delete_user_state, save_state, using_supabase
from app.tenancy import ensure_user_directories, get_user_paths, normalize_user_id


_PROFILE_NAMESPACE = "profile_memories"


def _atomic_json_write(path: Path, payload: Any) -> None:
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


def save_user_profile_memories(
    user_id: str,
    memories: list[dict[str, Any]],
) -> Path:
    """Validate then replace one user's profile-memory source of truth."""
    normalized = normalize_user_id(user_id)
    validated = validate_profile_memories(memories)
    paths = ensure_user_directories(normalized)

    if using_supabase():
        save_state(normalized, _PROFILE_NAMESPACE, validated)
        # Keep a disposable local mirror for UI paths that only need an existence hint.
        _atomic_json_write(paths.profile_memories, validated)
    else:
        _atomic_json_write(paths.profile_memories, validated)

    if paths.memory_index.exists():
        shutil.rmtree(paths.memory_index)
    clear_profile_vector_store_cache()
    return paths.profile_memories


def load_user_profile_memories(user_id: str) -> list[dict[str, Any]]:
    return load_profile_memories(user_id=user_id)


def export_user_data(user_id: str) -> bytes:
    """Return a ZIP containing exportable data owned by the authenticated user."""
    normalized = normalize_user_id(user_id)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        try:
            profile = load_user_profile_memories(normalized)
        except FileNotFoundError:
            profile = []
        if profile:
            archive.writestr(
                "profile_memories.json",
                json.dumps(profile, indent=2, ensure_ascii=False),
            )

        applications = [
            record.model_dump()
            for record in load_application_records(user_id=normalized)
        ]
        if applications:
            archive.writestr(
                "applications.json",
                json.dumps(applications, indent=2, ensure_ascii=False),
            )
    return buffer.getvalue()


def delete_user_data(user_id: str) -> None:
    """Delete one user's persistent state and disposable local workspace."""
    normalized = normalize_user_id(user_id)
    if using_supabase():
        delete_user_state(normalized)

    paths = get_user_paths(normalized)
    if paths.root.exists():
        shutil.rmtree(paths.root)
    clear_profile_vector_store_cache()
