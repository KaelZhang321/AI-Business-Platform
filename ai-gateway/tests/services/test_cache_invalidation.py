from __future__ import annotations

import importlib
import sys
from types import SimpleNamespace


def _load_module():
    sys.modules.setdefault("aio_pika", SimpleNamespace(connect_robust=None))
    return importlib.import_module("app.services.cache_invalidation")


def test_invalidate_rag_cache_clears_all_entries() -> None:
    cache_invalidation = _load_module()
    cache = cache_invalidation.get_rag_cache()
    cache.clear()
    cache["rag:customer:a"] = {"value": 1}
    cache["rag:customer:b"] = {"value": 2}

    cleared = cache_invalidation.invalidate_rag_cache()

    assert cleared == 2
    assert cache == {}


def test_invalidate_rag_cache_supports_category_filter() -> None:
    cache_invalidation = _load_module()
    cache = cache_invalidation.get_rag_cache()
    cache.clear()
    cache["rag:customer:a"] = {"value": 1}
    cache["rag:exam:b"] = {"value": 2}

    cleared = cache_invalidation.invalidate_rag_cache("customer")

    assert cleared == 1
    assert "rag:customer:a" not in cache
    assert "rag:exam:b" in cache


def test_invalidate_semantic_cache_without_service_returns_zero() -> None:
    cache_invalidation = _load_module()
    cache_invalidation.set_semantic_cache_service(None)

    assert cache_invalidation.invalidate_semantic_cache() == 0


def test_invalidate_semantic_cache_delegates_to_service() -> None:
    cache_invalidation = _load_module()

    class StubSemanticCache:
        def __init__(self) -> None:
            self.calls: list[int | None] = []

        def invalidate(self, kb_version: int | None = None) -> int:
            self.calls.append(kb_version)
            return 7

    stub = StubSemanticCache()
    cache_invalidation.set_semantic_cache_service(stub)

    result = cache_invalidation.invalidate_semantic_cache(42)

    assert result == 7
    assert stub.calls == [42]
