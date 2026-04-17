from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

from app.config import settings


def load_profile_memories(file_path: Path | None = None) -> list[dict[str, Any]]:
    """
    Load structured profile memories from a JSON file.
    """
    target_path = file_path or settings.profile_memories_path

    if not target_path.exists():
        raise FileNotFoundError(f"Profile memories file not found: {target_path}")

    with open(target_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("Profile memories JSON must contain a list of memory objects.")

    return data


def profile_memories_to_documents(memories: list[dict[str, Any]]) -> list[Document]:
    """
    Convert structured profile memories into LangChain Document objects.
    """
    documents: list[Document] = []

    for memory in memories:
        content = memory.get("content", "").strip()
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
    """
    Return the embeddings model used for profile memory retrieval.
    """
    return HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )


def build_profile_vector_store(
    memories: list[dict[str, Any]] | None = None,
) -> FAISS:
    """
    Build an in-memory FAISS vector store from profile memories.
    """
    if memories is None:
        memories = load_profile_memories()

    documents = profile_memories_to_documents(memories)
    embeddings = get_embeddings_model()

    if not documents:
        raise ValueError("No valid profile memories found to index.")

    vector_store = FAISS.from_documents(
        documents=documents,
        embedding=embeddings,
    )
    return vector_store


def save_profile_vector_store(vector_store: FAISS) -> None:
    """
    Persist the FAISS vector store locally.
    """
    settings.memory_index_path.mkdir(parents=True, exist_ok=True)
    vector_store.save_local(str(settings.memory_index_path))


def load_profile_vector_store() -> FAISS:
    """
    Load the persisted FAISS vector store from disk.
    """
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
    Load the vector store if the saved FAISS index exists,
    otherwise build and save it.
    """
    index_file = settings.memory_index_path / "index.faiss"
    store_file = settings.memory_index_path / "index.pkl"

    if index_file.exists() and store_file.exists():
        return load_profile_vector_store()

    vector_store = build_profile_vector_store()
    save_profile_vector_store(vector_store)
    return vector_store

def retrieve_profile_context(
    query: str,
    k: int = 4,
) -> list[Document]:
    """
    Retrieve the most relevant profile memories for a given query.
    """
    vector_store = get_or_create_profile_vector_store()
    return vector_store.similarity_search(query, k=k)