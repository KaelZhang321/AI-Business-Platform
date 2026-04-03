"""
API Catalog — 数据模型

ApiCatalogEntry: 单条接口目录记录（YAML → Pydantic → Milvus 向量记录）
ApiCatalogSearchResult: 带相似度分数的检索结果
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ParamSchema(BaseModel):
    """接口参数 JSON Schema（简化版，够用于 LLM 提取）。"""
    type: str = "object"
    properties: dict[str, dict[str, Any]] = Field(default_factory=dict)
    required: list[str] = Field(default_factory=list)


class ApiCatalogEntry(BaseModel):
    """单条业务接口目录记录。

    对应 config/api_catalog.yaml 中一个 api 条目，
    也对应 Milvus `api_catalog` collection 中一条向量记录。
    """

    # ---------- 标识 ----------
    id: str = Field(..., description="接口唯一标识，如 biz_customer_list_v1")

    # ---------- 检索用字段 ----------
    description: str = Field(..., description="接口自然语言描述（embedding 的主要内容）")
    example_queries: list[str] = Field(
        default_factory=list,
        description="覆盖用户可能的提问方式，扩充召回率",
    )
    tags: list[str] = Field(default_factory=list, description="接口标签（领域/分类）")

    # ---------- 调用元数据 ----------
    method: Literal["GET", "POST", "PUT", "DELETE", "PATCH"] = "GET"
    path: str = Field(..., description="相对于 business_server_url 的接口路径，如 /api/customer/list")
    auth_required: bool = True
    version: str = "v1"

    # ---------- 参数提取 ----------
    param_schema: ParamSchema = Field(
        default_factory=ParamSchema,
        description="接口参数 JSON Schema，供 LLM 参数提取使用",
    )

    # ---------- 响应规范化 ----------
    response_data_path: str = Field(
        default="data",
        description="响应 JSON 中数据列表的路径，用 '.' 分隔，如 data.list",
    )
    field_labels: dict[str, str] = Field(
        default_factory=dict,
        description="响应字段名 → 中文 label 映射",
    )

    # ---------- UI 渲染提示 ----------
    ui_hint: Literal["table", "card", "metric", "list", "chart"] = "table"

    # ---------- 向量（Milvus 回填，入库前不填）----------
    embedding: list[float] | None = Field(None, exclude=True)

    @property
    def embed_text(self) -> str:
        """生成用于 embedding 的文本（描述 + 示例问法）。"""
        parts = [self.description]
        if self.example_queries:
            parts.extend(self.example_queries)
        if self.tags:
            parts.append(" ".join(self.tags))
        return "\n".join(parts)


class ApiCatalogSearchResult(BaseModel):
    """带相似度分数的接口检索结果。"""
    entry: ApiCatalogEntry
    score: float = Field(..., description="向量相似度分数（0-1，越高越相关）")
