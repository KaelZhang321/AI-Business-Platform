"""
API Catalog — 数据模型

ApiCatalogEntry: 单条接口目录记录（YAML → Pydantic → Milvus 向量记录）
ApiCatalogSearchResult: 带相似度分数的检索结果
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ParamSchema(BaseModel):
    """接口参数 Schema 的最小子集。

    功能：
        只保留第二阶段参数提取真正需要的字段，避免把完整 OpenAPI schema 全量塞给 LLM。
    """
    type: str = "object"
    properties: dict[str, dict[str, Any]] = Field(default_factory=dict)
    required: list[str] = Field(default_factory=list)


class ApiCatalogDetailHint(BaseModel):
    """详情页运行时提示。"""

    enabled: bool = False
    api_id: str | None = Field(None, description="详情查询使用的接口 ID")
    identifier_field: str | None = Field(None, description="详情主键字段")
    query_param: str | None = Field(None, description="详情查询参数名")
    ui_action: str = Field("remoteQuery", description="推荐的前端动作")
    template_code: str | None = Field(None, description="预设详情模板编码")
    fallback_mode: str = Field("dynamic_ui", description="模板未命中的回退模式")


class ApiCatalogPaginationHint(BaseModel):
    """分页运行时提示。"""

    enabled: bool = False
    api_id: str | None = Field(None, description="分页刷新使用的接口 ID")
    page_param: str = Field("pageNum", description="页码参数名")
    page_size_param: str = Field("pageSize", description="分页大小参数名")
    ui_action: str = Field("remoteQuery", description="推荐的前端动作")
    mutation_target: str | None = Field(None, description="前端局部刷新目标")


class ApiCatalogTemplateHint(BaseModel):
    """模板快路提示。"""

    enabled: bool = False
    template_code: str | None = Field(None, description="模板编码")
    render_mode: str = Field("dynamic_ui", description="模板渲染模式")
    fallback_mode: str = Field("dynamic_ui", description="模板未命中的回退模式")


class ApiCatalogSearchFilters(BaseModel):
    """Milvus 标量过滤器。"""

    domains: list[str] = Field(default_factory=list)
    envs: list[str] = Field(default_factory=list)
    statuses: list[str] = Field(default_factory=list)
    tag_names: list[str] = Field(default_factory=list)


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
    domain: str = Field("generic", description="接口所属业务域")
    env: str = Field("shared", description="接口所属环境")
    status: Literal["active", "inactive", "deprecated"] = "active"
    tag_name: str | None = Field(None, description="更稳定的一级业务标签")
    business_intents: list[str] = Field(
        default_factory=lambda: ["query_business_data"],
        description="该接口可支持的业务意图编码",
    )

    # ---------- 调用元数据 ----------
    method: Literal["GET", "POST", "PUT", "DELETE", "PATCH"] = "GET"
    path: str = Field(..., description="相对于 business_server_url 的接口路径，如 /api/customer/list")
    auth_required: bool = True
    version: str = "v1"
    executor_config: dict[str, Any] = Field(default_factory=dict, description="执行器附加配置")
    security_rules: dict[str, Any] = Field(default_factory=dict, description="安全规则元数据")

    # ---------- 参数提取 ----------
    param_schema: ParamSchema = Field(
        default_factory=ParamSchema,
        description="接口参数 JSON Schema，供 LLM 参数提取使用",
    )
    response_schema: dict[str, Any] = Field(
        default_factory=dict,
        description="接口响应 JSON Schema，供 LLM 理解返回结构与字段层级",
    )
    sample_request: dict[str, Any] = Field(
        default_factory=dict,
        description="接口示例请求，用于提示 LLM 更贴近真实参数形状",
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
    detail_hint: ApiCatalogDetailHint = Field(default_factory=ApiCatalogDetailHint)
    pagination_hint: ApiCatalogPaginationHint = Field(default_factory=ApiCatalogPaginationHint)
    template_hint: ApiCatalogTemplateHint = Field(default_factory=ApiCatalogTemplateHint)

    # ---------- 向量（Milvus 回填，入库前不填）----------
    embedding: list[float] | None = Field(None, exclude=True)

    @property
    def embed_text(self) -> str:
        """生成 embedding 文本。

        功能：
            把语义描述、业务域、标签、业务意图压成一段检索文本，兼顾召回率与过滤稳定性。
        """
        parts = [self.description, f"domain:{self.domain}", f"status:{self.status}"]
        if self.example_queries:
            parts.extend(self.example_queries)
        if self.tags:
            parts.append(" ".join(self.tags))
        if self.tag_name:
            parts.append(self.tag_name)
        if self.business_intents:
            parts.append(" ".join(self.business_intents))
        return "\n".join(parts)

    @property
    def api_path(self) -> str:
        """兼容第一阶段命名习惯的别名字段。"""
        return self.path

    @property
    def api_schema(self) -> dict[str, Any]:
        """输出给 LLM 的稳定接口说明书契约。

        功能：
            对齐设计文档中 `api_schema` 的职责，明确区分给 LLM 使用的说明书
            与给执行器使用的 `executor_config`。这里保留请求/响应主体，并额外
            附带网关运行时必需的裁剪提示，避免后续链路再去猜响应展开路径。
        """
        return {
            "request": self.param_schema.model_dump(),
            "response_schema": self.response_schema,
            "sample_request": self.sample_request,
            "response_data_path": self.response_data_path,
            "field_labels": self.field_labels,
        }


class ApiCatalogSearchResult(BaseModel):
    """带相似度分数的接口检索结果。"""
    entry: ApiCatalogEntry
    score: float = Field(..., description="向量相似度分数（0-1，越高越相关）")
