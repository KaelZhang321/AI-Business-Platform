"""
API Catalog 包

业务接口 RAG 向量库的核心服务包，提供：
- schema: ApiCatalogEntry 数据模型
- indexer: YAML 目录 → Milvus 向量入库
- retriever: 用户查询 → 语义检索候选接口
- param_extractor: LLM 从用户输入提取接口参数
- executor: httpx 调用 business-server 并规范化响应
"""
from app.services.api_catalog.schema import ApiCatalogEntry, ApiCatalogSearchResult

__all__ = ["ApiCatalogEntry", "ApiCatalogSearchResult"]
