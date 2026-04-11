# 04-04 SUMMARY

## 完成内容

1. 落地了 Stage 2 混合召回器：
   - [hybrid_retriever.py](/Users/smart/PycharmProjects/AI-Business-Platform/ai-gateway/app/services/api_catalog/hybrid_retriever.py) 新增 `ApiCatalogHybridRetriever`
   - 召回顺序固定为“Milvus 锚点 -> Redis Graph Cache -> Neo4j 子图 -> support API 回填”
2. 实现了单次 Cypher 主路径与原始遍历兜底：
   - [graph_repository.py](/Users/smart/PycharmProjects/AI-Business-Platform/ai-gateway/app/services/api_catalog/graph_repository.py) 的 `fetch_subgraph()` 现在会优先走 `COMPANION` 剪枝查询
   - 当 `COMPANION` 没有命中 support API 时，会回退到 `CONSUMES -> Field <- PRODUCES` 原始遍历
3. 接入了 Graph Cache 与 singleflight 护栏：
   - [graph_cache.py](/Users/smart/PycharmProjects/AI-Business-Platform/ai-gateway/app/services/api_catalog/graph_cache.py) 负责子图缓存与单飞锁
   - `ApiCatalogHybridRetriever` 在未拿到单飞锁时优先等缓存，不再并发回源打爆图仓储
4. 保留了现有 `/api-query` 调用面：
   - [api_query.py](/Users/smart/PycharmProjects/AI-Business-Platform/ai-gateway/app/api/routes/api_query.py) 已把进程级检索依赖切到 `ApiCatalogHybridRetriever`
   - 对 workflow 仍然保持 `search_stratified()` 返回候选列表的契约，但额外暴露了 `subgraph` 结果，供后续 Wave 3/4 接入
5. 补齐了 support API 元数据回填能力：
   - [retriever.py](/Users/smart/PycharmProjects/AI-Business-Platform/ai-gateway/app/services/api_catalog/retriever.py) 新增 `get_many_by_ids()`，避免 Stage 2 为 support API 做串行查询

## 关键产物

- [hybrid_retriever.py](/Users/smart/PycharmProjects/AI-Business-Platform/ai-gateway/app/services/api_catalog/hybrid_retriever.py)
- [graph_repository.py](/Users/smart/PycharmProjects/AI-Business-Platform/ai-gateway/app/services/api_catalog/graph_repository.py)
- [retriever.py](/Users/smart/PycharmProjects/AI-Business-Platform/ai-gateway/app/services/api_catalog/retriever.py)
- [api_query.py](/Users/smart/PycharmProjects/AI-Business-Platform/ai-gateway/app/api/routes/api_query.py)
- [test_api_catalog_hybrid_retriever.py](/Users/smart/PycharmProjects/AI-Business-Platform/ai-gateway/tests/services/test_api_catalog_hybrid_retriever.py)

## 验证结果

- `cd ai-gateway && .venv/bin/python -m compileall app/services/api_catalog/hybrid_retriever.py app/services/api_catalog/retriever.py app/api/routes/api_query.py`
- `cd ai-gateway && .venv/bin/ruff check app/services/api_catalog/hybrid_retriever.py app/services/api_catalog/retriever.py app/api/routes/api_query.py tests/services/test_api_catalog_hybrid_retriever.py`
- `cd ai-gateway && .venv/bin/python -m pytest tests/services/test_api_catalog_hybrid_retriever.py tests/services/test_api_query_workflow.py -q`

结果：
- compile 通过
- ruff 通过
- 混合召回 / singleflight / workflow 回归测试通过

## 结果说明

Stage 2 已经从“只返回语义相似接口列表”升级为“能缓存、能兜底、能带回字段路径的局部子图召回”。当前 workflow 还主要消费候选列表，但子图结果已经具备后续接到 planner / validator 的能力。
