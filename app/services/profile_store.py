from __future__ import annotations

import io
import json
import os
import shutil
import zipfile
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from app.memory import clear_profile_vector_store_cache, load_profile_memories
from app.tenancy import ensure_user_directories, get_user_paths


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
    """Validate then atomically replace one user's profile-memory source of truth."""
    paths = ensure_user_directories(user_id)
    validation_file = paths.root / ".profile_memories.validation.json"
    _atomic_json_write(validation_file, memories)
    try:
        validated = load_profile_memories(file_path=validation_file)
    finally:
        validation_file.unlink(missing_ok=True)

    _atomic_json_write(paths.profile_memories, validated)
    if paths.memory_index.exists():
        shutil.rmtree(paths.memory_index)
    clear_profile_vector_store_cache()
    return paths.profile_memories


def load_user_profile_memories(user_id: str) -> list[dict[str, Any]]:
    return load_profile_memories(user_id=user_id)


def export_user_data(user_id: str) -> bytes:
    """Return a ZIP containing only exportable data owned by the authenticated user."""
    paths = get_user_paths(user_id)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path, archive_name in (
            (paths.profile_memories, "profile_memories.json"),
            (paths.applications, "applications.json"),
        ):
            if path.exists():
                archive.write(path, archive_name)
    return buffer.getvalue()


def delete_user_data(user_id: str) -> None:
    """Delete the authenticated user's private workspace, including OAuth tokens."""
    paths = get_user_paths(user_id)
    if paths.root.exists():
        shutil.rmtree(paths.root)
    clear_profile_vector_store_cache()
