from __future__ import annotations

import pytest

from app.services.rag_service import RAGService
from app.services.semantic_cache import SemanticCacheService


class _FakeEmbedder:
    def encode(self, texts: list[str]) -> dict[str, list[list[float]]]:
        assert texts
        return {"dense_vecs": [_FakeVector()]}


class _FakeVector(list):
    def __init__(self) -> None:
        super().__init__([0.1, 0.2, 0.3])

    def tolist(self) -> list[float]:
        return list(self)


class _FakeCollection:
    def __init__(self) -> None:
        self.search_calls = 0
        self.delete_calls = 0
        self.insert_calls = 0
        self.flush_calls = 0
        self._num_entities = 0

    def search(self, **kwargs):  # noqa: ANN003, ANN201
        self.search_calls += 1
        assert kwargs["data"] == [[0.1, 0.2, 0.3]]
        return [[]]

    def delete(self, **kwargs):  # noqa: ANN003, ANN201
        self.delete_calls += 1
        return None

    def insert(self, rows):  # noqa: ANN201
        self.insert_calls += 1
        self._num_entities += 1
        return rows

    def flush(self):  # noqa: ANN201
        self.flush_calls += 1
        return None

    @property
    def num_entities(self) -> int:
        return self._num_entities


class _FakeReranker:
    def compute_score(self, pairs: list[list[str]]) -> list[float]:
        return [0.9 for _ in pairs]


@pytest.mark.asyncio
async def test_rag_vector_search_uses_async_wrapped_sync_clients(monkeypatch: pytest.MonkeyPatch) -> None:
    service = RAGService()
    collection = _FakeCollection()
    to_thread_calls: list[str] = []

    async def fake_to_thread(func, *args, **kwargs):  # noqa: ANN001, ANN202
        to_thread_calls.append(getattr(func, "__name__", repr(func)))
        return func(*args, **kwargs)

    monkeypatch.setattr("app.services.rag_service.asyncio.to_thread", fake_to_thread)
    monkeypatch.setattr(service, "_embedder", lambda: _FakeEmbedder())
    monkeypatch.setattr(service, "_milvus", lambda: collection)

    result = await service._vector_search("测试", None)

    assert result == []
    assert to_thread_calls == ["encode", "search"]
    assert collection.search_calls == 1


@pytest.mark.asyncio
async def test_rag_rerank_uses_async_wrapped_reranker(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.models.schemas import KnowledgeResult

    service = RAGService()
    to_thread_calls: list[str] = []

    async def fake_to_thread(func, *args, **kwargs):  # noqa: ANN001, ANN202
        to_thread_calls.append(getattr(func, "__name__", repr(func)))
        return func(*args, **kwargs)

    monkeypatch.setattr("app.services.rag_service.asyncio.to_thread", fake_to_thread)
    monkeypatch.setattr(service, "_reranker_model", lambda: _FakeReranker())

    docs = [KnowledgeResult(doc_id="1", title="t", content="c", score=0.1, doc_type="doc", metadata={})]
    result = await service._rerank("q", docs, top_k=1)

    assert result[0].metadata["rerank_score"] == 0.9
    assert to_thread_calls == ["compute_score"]


@pytest.mark.asyncio
async def test_semantic_cache_lookup_wraps_embed_and_search(monkeypatch: pytest.MonkeyPatch) -> None:
    service = SemanticCacheService()
    collection = _FakeCollection()
    to_thread_calls: list[str] = []

    async def fake_to_thread(func, *args, **kwargs):  # noqa: ANN001, ANN202
        to_thread_calls.append(getattr(func, "__name__", repr(func)))
        return func(*args, **kwargs)

    monkeypatch.setattr("app.services.semantic_cache.asyncio.to_thread", fake_to_thread)
    monkeypatch.setattr("app.services.semantic_cache.settings.semantic_cache_enabled", True)
    monkeypatch.setattr(service, "_get_embedder", lambda: _FakeEmbedder())
    monkeypatch.setattr(service, "_ensure_collection", lambda: collection)

    assert await service.lookup("测试") is None
    assert to_thread_calls == ["_embed", "search"]


@pytest.mark.asyncio
async def test_semantic_cache_store_wraps_mutating_sync_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    service = SemanticCacheService()
    collection = _FakeCollection()
    to_thread_calls: list[str] = []

    async def fake_to_thread(func, *args, **kwargs):  # noqa: ANN001, ANN202
        to_thread_calls.append(getattr(func, "__name__", repr(func)))
        return func(*args, **kwargs)

    monkeypatch.setattr("app.services.semantic_cache.asyncio.to_thread", fake_to_thread)
    monkeypatch.setattr("app.services.semantic_cache.settings.semantic_cache_enabled", True)
    monkeypatch.setattr(service, "_get_embedder", lambda: _FakeEmbedder())
    monkeypatch.setattr(service, "_ensure_collection", lambda: collection)

    await service.store("测试", "回答", [])

    assert to_thread_calls == ["_embed", "delete", "<lambda>", "insert", "flush"]
    assert collection.delete_calls == 1
    assert collection.insert_calls == 1
    assert collection.flush_calls == 1
