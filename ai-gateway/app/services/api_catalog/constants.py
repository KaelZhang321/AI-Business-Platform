"""API Catalog 共享常量。

功能：
    这层模块专门承载 runtime 与 indexing 共同依赖、但又不属于任何单一入口实现的常量。
    之所以单独拆出来，是为了避免运行时检索器再去 import `indexer.py` 这种离线入口文件，
    从而把“共享事实”误绑到“离线执行入口”上。
"""

from __future__ import annotations

# Milvus collection 名称（独立于知识库 collection，避免污染）
API_CATALOG_COLLECTION = "api_catalog"

# BGE-M3 dense vector 维度
EMBEDDING_DIM = 1024

