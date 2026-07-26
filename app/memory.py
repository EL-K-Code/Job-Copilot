from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

from app.config import settings
from app.tenancy import get_user_paths

logger = logging.getLogger(__name__)


def _memory_paths(user_id: str | None = None) -> tuple[Path, Path]:
    if user_id is None:
        return settings.profile_memories_path, settings.memory_index_path
    paths = get_user_paths(user_id)
    return paths.profile_memories, paths.memory_index


def load_profile_memories(
    file_path: Path | None = None,
    *,
    user_id: str | None = None,
) -> list[dict[str, Any]]:
    """Load and validate structured profile memories from a JSON file."""
    target_path = file_path or _memory_paths(user_id)[0]

    if not target_path.exists():
        raise FileNotFoundError(f"Profile memories file not found: {target_path}")

    with open(target_path, "r", encoding="utf-8") as file_handle:
        data = json.load(file_handle)

    if not isinstance(data, list):
        raise ValueError("Profile memories JSON must contain a list of memory objects.")

    seen_ids: set[str] = set()
    for index, memory in enumerate(data, start=1):
        if not isinstance(memory, dict):
            raise ValueError(f"Profile memory {index} must be a JSON object.")
        memory_id = str(memory.get("id", "")).strip()
        memory_type = str(memory.get("type", "")).strip()
        content = str(memory.get("content", "")).strip()
        if not memory_id or not memory_type or not content:
            raise ValueError(
                f"Profile memory {index} must contain non-empty id, type and content fields."
            )
        if memory_id in seen_ids:
            raise ValueError(f"Profile memories contain duplicate id: {memory_id}")
        seen_ids.add(memory_id)

    return data


def profile_memories_to_documents(memories: list[dict[str, Any]]) -> list[Document]:
    """Convert structured profile memories into documents without losing audit metadata."""
    documents: list[Document] = []

    for memory in memories:
        content = str(memory.get("content", "")).strip()
        if not content:
            continue

        metadata = {
            str(key): value
            for key, value in memory.items()
            if key != "content" and value is not None
        }

        documents.append(Document(page_content=content, metadata=metadata))

    return documents


def get_embeddings_model() -> HuggingFaceEmbeddings:
    """Return the embeddings model used for profile-memory retrieval."""
    return HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")


def build_profile_vector_store(
    memories: list[dict[str, Any]] | None = None,
    *,
    user_id: str | None = None,
) -> FAISS:
    """Build an in-memory FAISS vector store from one user's profile memories."""
    if memories is None:
        memories = load_profile_memories(user_id=user_id)

    documents = profile_memories_to_documents(memories)
    embeddings = get_embeddings_model()

    if not documents:
        raise ValueError("No valid profile memories found to index.")

    return FAISS.from_documents(documents=documents, embedding=embeddings)


def save_profile_vector_store(
    vector_store: FAISS,
    *,
    user_id: str | None = None,
) -> None:
    """Persist a locally generated FAISS vector store in the owning user's directory."""
    index_path = _memory_paths(user_id)[1]
    index_path.mkdir(parents=True, exist_ok=True)
    vector_store.save_local(str(index_path))


def load_profile_vector_store(*, user_id: str | None = None) -> FAISS:
    """Load a trusted locally generated FAISS store when explicitly enabled."""
    if not settings.allow_trusted_faiss_deserialization:
        raise RuntimeError(
            "Loading a persisted FAISS store is disabled by default because the "
            "LangChain store includes pickle data. Rebuild from profile memories JSON "
            "or set ALLOW_TRUSTED_FAISS_DESERIALIZATION=true only for an index that "
            "you generated locally and trust."
        )

    index_path = _memory_paths(user_id)[1]
    embeddings = get_embeddings_model()

    if not index_path.exists():
        raise FileNotFoundError(f"Vector store directory not found: {index_path}")

    return FAISS.load_local(
        folder_path=str(index_path),
        embeddings=embeddings,
        allow_dangerous_deserialization=True,
    )


@lru_cache(maxsize=64)
def _get_or_create_profile_vector_store_cached(
    profile_path_str: str,
    index_path_str: str,
    allow_trusted_deserialization: bool,
) -> FAISS:
    profile_path = Path(profile_path_str)
    index_path = Path(index_path_str)
    index_file = index_path / "index.faiss"
    store_file = index_path / "index.pkl"
    persisted_store_exists = index_file.exists() and store_file.exists()

    if persisted_store_exists and allow_trusted_deserialization:
        embeddings = get_embeddings_model()
        return FAISS.load_local(
            folder_path=str(index_path),
            embeddings=embeddings,
            allow_dangerous_deserialization=True,
        )

    if persisted_store_exists:
        logger.warning(
            "A persisted FAISS store exists but trusted deserialization is disabled; "
            "rebuilding the in-memory index from profile memories JSON."
        )

    memories = load_profile_memories(file_path=profile_path)
    vector_store = build_profile_vector_store(memories)

    if allow_trusted_deserialization:
        index_path.mkdir(parents=True, exist_ok=True)
        vector_store.save_local(str(index_path))

    return vector_store


def get_or_create_profile_vector_store(*, user_id: str | None = None) -> FAISS:
    """Return a process-cached vector store keyed by the owning user's private paths."""
    profile_path, index_path = _memory_paths(user_id)
    return _get_or_create_profile_vector_store_cached(
        str(profile_path.resolve()),
        str(index_path.resolve()),
        settings.allow_trusted_faiss_deserialization,
    )


def clear_profile_vector_store_cache() -> None:
    """Clear all process caches after any user's profile memories are changed."""
    _get_or_create_profile_vector_store_cached.cache_clear()


def retrieve_profile_context_with_scores(
    query: str,
    k: int = 4,
    *,
    user_id: str | None = None,
) -> list[tuple[Document, float]]:
    """Retrieve profile memories and raw FAISS distances for one user only."""
    normalized_query = query.strip()
    if not normalized_query:
        raise ValueError("The retrieval query cannot be empty.")
    if k < 1:
        raise ValueError("k must be greater than or equal to 1.")

    vector_store = get_or_create_profile_vector_store(user_id=user_id)
    return vector_store.similarity_search_with_score(normalized_query, k=k)


def retrieve_profile_context(
    query: str,
    k: int = 4,
    *,
    user_id: str | None = None,
) -> list[Document]:
    """Retrieve the most relevant memories from exactly one user's profile."""
    return [
        document
        for document, _score in retrieve_profile_context_with_scores(
            query,
            k=k,
            user_id=user_id,
        )
    ]
