from __future__ import annotations

from langchain_core.documents import Document

from app import retrieval


def _document(memory_id: str, content: str) -> Document:
    return Document(
        page_content=content,
        metadata={"id": memory_id, "type": "project"},
    )


def test_bm25_ranks_exact_technical_evidence_first():
    documents = [
        _document("m1", "Built APIs with FastAPI and Docker."),
        _document("m2", "Implemented RAG semantic retrieval with FAISS embeddings."),
        _document("m3", "Used SQL for analytics and reporting."),
    ]

    ranked = retrieval.rank_bm25_documents("RAG FAISS retrieval", documents)

    assert ranked
    assert ranked[0][0].metadata["id"] == "m2"
    assert ranked[0][1] > 0


def test_reciprocal_rank_fusion_rewards_cross_retriever_agreement():
    scores = retrieval.reciprocal_rank_fusion(
        [["a", "b", "c"], ["b", "c", "d"]],
        rrf_k=60,
    )

    assert scores["b"] > scores["a"]
    assert scores["b"] > scores["d"]


def test_hybrid_retrieval_can_recover_sparse_only_candidate(monkeypatch):
    memories = [
        {"id": "m1", "type": "project", "content": "Built Python APIs."},
        {"id": "m2", "type": "experience", "content": "Worked on data pipelines."},
        {
            "id": "m3",
            "type": "project",
            "content": "Implemented FAISS retrieval for a RAG system.",
        },
    ]
    dense_hits = [
        (_document("m1", "Built Python APIs."), 0.10),
        (_document("m2", "Worked on data pipelines."), 0.20),
    ]

    monkeypatch.setattr(retrieval, "load_profile_memories", lambda user_id=None: memories)
    monkeypatch.setattr(
        retrieval,
        "retrieve_dense_profile_context_with_scores",
        lambda query, k, user_id=None: dense_hits[:k],
    )

    results = retrieval.retrieve_profile_context_hybrid(
        "FAISS RAG retrieval",
        k=3,
        candidate_k=3,
        rerank=False,
    )

    by_id = {document.metadata["id"]: document for document in results}
    assert set(by_id) == {"m1", "m2", "m3"}
    assert by_id["m3"].metadata["retrieval_sparse_rank"] == 1
    assert "retrieval_dense_rank" not in by_id["m3"].metadata
    assert by_id["m1"].metadata["retrieval_dense_rank"] == 1
    assert all(
        document.metadata["retrieval_strategy"] == "hybrid_rrf"
        for document in results
    )


def test_cross_encoder_reranker_reorders_fused_candidates(monkeypatch):
    documents = [
        Document(
            page_content="General Python engineering.",
            metadata={"id": "m1", "retrieval_fusion_score": 0.03},
        ),
        Document(
            page_content="Direct evidence for the requested capability.",
            metadata={"id": "m2", "retrieval_fusion_score": 0.02},
        ),
    ]

    class FakeReranker:
        def predict(self, pairs, show_progress_bar=False):
            assert len(pairs) == 2
            assert show_progress_bar is False
            return [0.1, 2.0]

    monkeypatch.setattr(
        retrieval,
        "get_cross_encoder_reranker",
        lambda _model_name: FakeReranker(),
    )

    reranked = retrieval.rerank_documents(
        "requested capability",
        documents,
        model_name="fake-reranker",
    )

    assert [document.metadata["id"] for document in reranked] == ["m2", "m1"]
    assert reranked[0].metadata["retrieval_reranker_applied"] is True
    assert reranked[0].metadata["retrieval_reranker_score"] == 2.0


def test_cross_encoder_failure_falls_back_to_fused_order(monkeypatch):
    documents = [
        Document(
            page_content="First fused candidate.",
            metadata={"id": "m1", "retrieval_fusion_score": 0.03},
        ),
        Document(
            page_content="Second fused candidate.",
            metadata={"id": "m2", "retrieval_fusion_score": 0.02},
        ),
    ]

    class BrokenReranker:
        def predict(self, _pairs, show_progress_bar=False):
            raise RuntimeError("synthetic failure")

    monkeypatch.setattr(
        retrieval,
        "get_cross_encoder_reranker",
        lambda _model_name: BrokenReranker(),
    )

    reranked = retrieval.rerank_documents(
        "query",
        documents,
        model_name="fake-reranker",
    )

    assert [document.metadata["id"] for document in reranked] == ["m1", "m2"]
    assert all(
        document.metadata["retrieval_reranker_applied"] is False
        for document in reranked
    )


def test_dense_strategy_remains_available_as_explicit_baseline(monkeypatch):
    expected = [_document("m1", "Dense baseline result.")]
    captured = {}

    def fake_dense(query, k, user_id=None):
        captured.update({"query": query, "k": k, "user_id": user_id})
        return expected

    monkeypatch.setattr(retrieval, "retrieve_dense_profile_context", fake_dense)

    results = retrieval.retrieve_profile_context(
        "baseline query",
        k=1,
        user_id="tester",
        strategy="dense",
    )

    assert results == expected
    assert captured == {"query": "baseline query", "k": 1, "user_id": "tester"}
