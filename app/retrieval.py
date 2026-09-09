from __future__ import annotations

import hashlib
import logging
import math
import re
import unicodedata
from collections import Counter
from functools import lru_cache
from typing import Iterable

from langchain_core.documents import Document
from sentence_transformers import CrossEncoder

from app.config import settings
from app.memory import (
    load_profile_memories,
    profile_memories_to_documents,
    retrieve_profile_context as retrieve_dense_profile_context,
    retrieve_profile_context_with_scores as retrieve_dense_profile_context_with_scores,
)


logger = logging.getLogger(__name__)
_TOKEN_PATTERN = re.compile(r"[a-z0-9][a-z0-9+#.]*", re.IGNORECASE)


def _normalize_text(value: str) -> str:
    text = unicodedata.normalize("NFKC", str(value)).casefold()
    text = text.replace("&", " and ")
    text = re.sub(r"[-_/]", " ", text)
    return " ".join(text.split())


def _tokenize(value: str) -> list[str]:
    """Tokenize technical text for sparse retrieval without external state."""
    return _TOKEN_PATTERN.findall(_normalize_text(value))


def _document_key(document: Document) -> str:
    memory_id = str(document.metadata.get("id", "")).strip()
    if memory_id:
        return f"id:{memory_id}"
    digest = hashlib.sha256(document.page_content.encode("utf-8")).hexdigest()
    return f"content:{digest}"


def _copy_document(document: Document, **metadata: object) -> Document:
    merged = dict(document.metadata)
    merged.update(metadata)
    return Document(page_content=document.page_content, metadata=merged)


def rank_bm25_documents(
    query: str,
    documents: list[Document],
    *,
    k1: float = 1.5,
    b: float = 0.75,
) -> list[tuple[Document, float]]:
    """Rank profile memories with a compact, deterministic BM25 implementation."""
    normalized_query = query.strip()
    if not normalized_query:
        raise ValueError("The retrieval query cannot be empty.")
    if not documents:
        return []

    query_terms = Counter(_tokenize(normalized_query))
    if not query_terms:
        return []

    tokenized_documents = [_tokenize(document.page_content) for document in documents]
    document_lengths = [len(tokens) for tokens in tokenized_documents]
    average_length = sum(document_lengths) / len(document_lengths)
    if average_length <= 0:
        return []

    document_frequency: Counter[str] = Counter()
    for tokens in tokenized_documents:
        document_frequency.update(set(tokens))

    number_of_documents = len(documents)
    scored: list[tuple[Document, float]] = []
    for document, tokens, document_length in zip(
        documents,
        tokenized_documents,
        document_lengths,
        strict=True,
    ):
        term_frequency = Counter(tokens)
        score = 0.0
        for term, query_frequency in query_terms.items():
            tf = term_frequency.get(term, 0)
            if tf <= 0:
                continue
            df = document_frequency.get(term, 0)
            idf = math.log(
                1.0
                + (number_of_documents - df + 0.5)
                / (df + 0.5)
            )
            denominator = tf + k1 * (
                1.0 - b + b * document_length / average_length
            )
            score += query_frequency * idf * (tf * (k1 + 1.0)) / denominator

        if score > 0:
            scored.append((document, float(score)))

    return sorted(
        scored,
        key=lambda item: (-item[1], _document_key(item[0])),
    )


def reciprocal_rank_fusion(
    rankings: Iterable[Iterable[str]],
    *,
    rrf_k: int = 60,
) -> dict[str, float]:
    """Fuse independent rankings without requiring calibrated raw scores."""
    if rrf_k < 1:
        raise ValueError("rrf_k must be greater than or equal to 1.")

    scores: dict[str, float] = {}
    for ranking in rankings:
        seen: set[str] = set()
        for rank, key in enumerate(ranking, start=1):
            normalized_key = str(key).strip()
            if not normalized_key or normalized_key in seen:
                continue
            seen.add(normalized_key)
            scores[normalized_key] = scores.get(normalized_key, 0.0) + 1.0 / (
                rrf_k + rank
            )
    return scores


@lru_cache(maxsize=2)
def get_cross_encoder_reranker(model_name: str) -> CrossEncoder:
    """Load one process-cached cross-encoder reranker lazily on first use."""
    return CrossEncoder(model_name, device="cpu")


def rerank_documents(
    query: str,
    documents: list[Document],
    *,
    model_name: str | None = None,
) -> list[Document]:
    """Rerank a small fused candidate pool with a cross encoder.

    The cross-encoder score is used only for ordering. It is not interpreted as a
    probability. If the optional reranker cannot be loaded or executed, retrieval
    fails open to the deterministic fused ranking instead of blocking an application.
    """
    if not documents:
        return []

    selected_model = (model_name or settings.retrieval_reranker_model).strip()
    try:
        reranker = get_cross_encoder_reranker(selected_model)
        pairs = [(query, document.page_content) for document in documents]
        raw_scores = reranker.predict(pairs, show_progress_bar=False)
        scores = [float(score) for score in raw_scores]
        if len(scores) != len(documents):
            raise RuntimeError("Cross-encoder returned an unexpected number of scores.")
    except Exception as exc:
        logger.warning(
            "Cross-encoder reranking unavailable (%s); using fused retrieval order.",
            type(exc).__name__,
        )
        return [
            _copy_document(
                document,
                retrieval_reranker_applied=False,
                retrieval_reranker_model=selected_model,
            )
            for document in documents
        ]

    scored_documents = [
        (
            _copy_document(
                document,
                retrieval_reranker_applied=True,
                retrieval_reranker_model=selected_model,
                retrieval_reranker_score=score,
            ),
            score,
        )
        for document, score in zip(documents, scores, strict=True)
    ]
    scored_documents.sort(
        key=lambda item: (
            -item[1],
            -float(item[0].metadata.get("retrieval_fusion_score", 0.0)),
            _document_key(item[0]),
        )
    )
    return [document for document, _score in scored_documents]


def retrieve_profile_context_hybrid(
    query: str,
    k: int = 4,
    *,
    user_id: str | None = None,
    candidate_k: int | None = None,
    rerank: bool | None = None,
) -> list[Document]:
    """Retrieve verified profile evidence with dense + BM25 + RRF + reranking."""
    normalized_query = query.strip()
    if not normalized_query:
        raise ValueError("The retrieval query cannot be empty.")
    if k < 1:
        raise ValueError("k must be greater than or equal to 1.")

    memories = load_profile_memories(user_id=user_id)
    all_documents = profile_memories_to_documents(memories)
    if not all_documents:
        return []

    pool_size = max(k, candidate_k or settings.retrieval_candidate_k)
    pool_size = min(pool_size, len(all_documents))

    dense_hits = retrieve_dense_profile_context_with_scores(
        normalized_query,
        k=pool_size,
        user_id=user_id,
    )
    sparse_hits = rank_bm25_documents(normalized_query, all_documents)[:pool_size]

    dense_ranks: dict[str, int] = {}
    dense_distances: dict[str, float] = {}
    sparse_ranks: dict[str, int] = {}
    sparse_scores: dict[str, float] = {}
    documents_by_key: dict[str, Document] = {}

    for rank, (document, distance) in enumerate(dense_hits, start=1):
        key = _document_key(document)
        documents_by_key[key] = document
        dense_ranks[key] = rank
        dense_distances[key] = float(distance)

    for rank, (document, score) in enumerate(sparse_hits, start=1):
        key = _document_key(document)
        documents_by_key.setdefault(key, document)
        sparse_ranks[key] = rank
        sparse_scores[key] = float(score)

    fusion_scores = reciprocal_rank_fusion(
        [dense_ranks.keys(), sparse_ranks.keys()],
        rrf_k=settings.retrieval_rrf_k,
    )
    ordered_keys = sorted(
        fusion_scores,
        key=lambda key: (
            -fusion_scores[key],
            dense_ranks.get(key, 10**9),
            sparse_ranks.get(key, 10**9),
            key,
        ),
    )

    fused_documents: list[Document] = []
    for fusion_rank, key in enumerate(ordered_keys, start=1):
        document = documents_by_key[key]
        metadata: dict[str, object] = {
            "retrieval_strategy": "hybrid_rrf",
            "retrieval_fusion_rank": fusion_rank,
            "retrieval_fusion_score": float(fusion_scores[key]),
        }
        if key in dense_ranks:
            metadata["retrieval_dense_rank"] = dense_ranks[key]
            metadata["retrieval_dense_distance"] = dense_distances[key]
        if key in sparse_ranks:
            metadata["retrieval_sparse_rank"] = sparse_ranks[key]
            metadata["retrieval_sparse_score"] = sparse_scores[key]
        fused_documents.append(_copy_document(document, **metadata))

    use_reranker = (
        settings.retrieval_reranker_enabled if rerank is None else bool(rerank)
    )
    if use_reranker and fused_documents:
        rerank_size = min(
            len(fused_documents),
            max(k, settings.retrieval_rerank_k),
        )
        reranked_head = rerank_documents(
            normalized_query,
            fused_documents[:rerank_size],
        )
        final_documents = reranked_head + fused_documents[rerank_size:]
    else:
        final_documents = [
            _copy_document(document, retrieval_reranker_applied=False)
            for document in fused_documents
        ]

    output: list[Document] = []
    for final_rank, document in enumerate(final_documents[:k], start=1):
        final_score = document.metadata.get("retrieval_reranker_score")
        if final_score is None:
            final_score = document.metadata.get("retrieval_fusion_score", 0.0)
        output.append(
            _copy_document(
                document,
                retrieval_strategy=(
                    "hybrid_rrf_cross_encoder"
                    if bool(document.metadata.get("retrieval_reranker_applied"))
                    else "hybrid_rrf"
                ),
                retrieval_final_rank=final_rank,
                retrieval_final_score=float(final_score),
            )
        )
    return output


def retrieve_profile_context(
    query: str,
    k: int = 4,
    *,
    user_id: str | None = None,
    strategy: str | None = None,
    rerank: bool | None = None,
) -> list[Document]:
    """Route profile retrieval through the configured production strategy."""
    selected_strategy = (strategy or settings.retrieval_strategy).strip().lower()
    if selected_strategy == "dense":
        return retrieve_dense_profile_context(query, k=k, user_id=user_id)
    if selected_strategy == "hybrid":
        return retrieve_profile_context_hybrid(
            query,
            k=k,
            user_id=user_id,
            rerank=rerank,
        )
    raise ValueError(
        f"Unsupported retrieval strategy: {selected_strategy}. "
        "Expected 'dense' or 'hybrid'."
    )


def retrieve_profile_context_with_scores(
    query: str,
    k: int = 4,
    *,
    user_id: str | None = None,
    strategy: str | None = None,
    rerank: bool | None = None,
) -> list[tuple[Document, float]]:
    """Return ranked documents with higher-is-better scores for benchmarking."""
    selected_strategy = (strategy or settings.retrieval_strategy).strip().lower()
    if selected_strategy == "dense":
        dense_hits = retrieve_dense_profile_context_with_scores(
            query,
            k=k,
            user_id=user_id,
        )
        return [(document, -float(distance)) for document, distance in dense_hits]

    documents = retrieve_profile_context(
        query,
        k=k,
        user_id=user_id,
        strategy=selected_strategy,
        rerank=rerank,
    )
    return [
        (document, float(document.metadata.get("retrieval_final_score", 0.0)))
        for document in documents
    ]
