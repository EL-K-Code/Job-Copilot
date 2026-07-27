from __future__ import annotations

from app import memory


def test_public_embeddings_model_is_anonymous_quiet_and_process_cached(monkeypatch):
    calls = []

    class FakeEmbeddings:
        def __init__(self, **kwargs):
            calls.append(kwargs)

    memory.get_embeddings_model.cache_clear()
    monkeypatch.setattr(memory, "HuggingFaceEmbeddings", FakeEmbeddings)

    first = memory.get_embeddings_model()
    second = memory.get_embeddings_model()

    assert first is second
    assert calls == [
        {
            "model_name": "sentence-transformers/all-MiniLM-L6-v2",
            "model_kwargs": {"token": False},
            "show_progress": False,
        }
    ]

    memory.get_embeddings_model.cache_clear()


def test_hugging_face_runtime_defaults_do_not_require_a_token():
    assert memory.os.environ["HF_HUB_DISABLE_TELEMETRY"] == "1"
    assert memory.os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] == "1"
    assert memory.os.environ["HF_HUB_VERBOSITY"] == "error"
    assert memory.os.environ["TOKENIZERS_PARALLELISM"] == "false"
