from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

from app.config import settings

logger = logging.getLogger(__name__)


def load_profile_memories(file_path: Path | None = None) -> list[dict[str, Any]]:
    """Load structured profile memories from a JSON file."""
    target_path = file_path or settings.profile_memories_path

    if not target_path.exists():
        raise FileNotFoundError(f"Profile memories file not found: {target_path}")

    with open(target_path, "r", encoding="utf-8") as file_handle:
        data = json.load(file_handle)

    if not isinstance(data, list):
        raise ValueError("Profile memories JSON must contain a list of memory objects.")

    return data


def profile_memories_to_documents(memories: list[dict[str, Any]]) -> list[Document]:
    """Convert structured profile memories into LangChain documents."""
    documents: list[Document] = []

    for memory in memories:
        content = str(memory.get("content", "")).strip()
        if not content:
            continue

        metadata = {
            "id": memory.get("id"),
            "type": memory.get("type"),
        }

        documents.append(
            Document(
                page_content=content,
                metadata=metadata,
            )
        )

    return documents


def get_embeddings_model() -> HuggingFaceEmbeddings:
    """Return the embeddings model used for profile-memory retrieval."""
    return HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )


def build_profile_vector_store(
    memories: list[dict[str, Any]] | None = None,
) -> FAISS:
    """Build an in-memory FAISS vector store from profile memories."""
    if memories is None:
        memories = load_profile_memories()

    documents = profile_memories_to_documents(memories)
    embeddings = get_embeddings_model()

    if not documents:
        raise ValueError("No valid profile memories found to index.")

    return FAISS.from_documents(
        documents=documents,
        embedding=embeddings,
    )


def save_profile_vector_store(vector_store: FAISS) -> None:
    """Persist a locally generated FAISS vector store."""
    settings.memory_index_path.mkdir(parents=True, exist_ok=True)
    vector_store.save_local(str(settings.memory_index_path))


def load_profile_vector_store() -> FAISS:
    """Load a trusted locally generated FAISS store when explicitly enabled."""
    if not settings.allow_trusted_faiss_deserialization:
        raise RuntimeError(
            "Loading a persisted FAISS store is disabled by default because the "
            "LangChain store includes pickle data. Rebuild from profile_memories.json "
            "or set ALLOW_TRUSTED_FAISS_DESERIALIZATION=true only for an index that "
            "you generated locally and trust."
        )

    embeddings = get_embeddings_model()

    if not settings.memory_index_path.exists():
        raise FileNotFoundError(
            f"Vector store directory not found: {settings.memory_index_path}"
        )

    return FAISS.load_local(
        folder_path=str(settings.memory_index_path),
        embeddings=embeddings,
        allow_dangerous_deserialization=True,
    )


def get_or_create_profile_vector_store() -> FAISS:
    """
    Load a trusted persisted store when explicitly allowed. Otherwise rebuild
    the in-memory index from the auditable JSON source of truth.
    """
    index_file = settings.memory_index_path / "index.faiss"
    store_file = settings.memory_index_path / "index.pkl"
    persisted_store_exists = index_file.exists() and store_file.exists()

    if persisted_store_exists and settings.allow_trusted_faiss_deserialization:
        return load_profile_vector_store()

    if persisted_store_exists:
        logger.warning(
            "A persisted FAISS store exists but trusted deserialization is disabled; "
            "rebuilding the in-memory index from profile_memories.json."
        )

    vector_store = build_profile_vector_store()

    if settings.allow_trusted_faiss_deserialization:
        save_profile_vector_store(vector_store)

    return vector_store


def retrieve_profile_context_with_scores(
    query: str,
    k: int = 4,
) -> list[tuple[Document, float]]:
    """Retrieve profile memories together with their raw FAISS distances."""
    normalized_query = query.strip()
    if not normalized_query:
        raise ValueError("The retrieval query cannot be empty.")
    if k < 1:
        raise ValueError("k must be greater than or equal to 1.")

    vector_store = get_or_create_profile_vector_store()
    return vector_store.similarity_search_with_score(normalized_query, k=k)


def retrieve_profile_context(
    query: str,
    k: int = 4,
) -> list[Document]:
    """Retrieve the most relevant profile memories for a query."""
    return [
        document
        for document, _score in retrieve_profile_context_with_scores(query, k=k)
    ]
