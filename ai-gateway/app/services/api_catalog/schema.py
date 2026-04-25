"""
API Catalog — 数据模型

ApiCatalogEntry: 单条接口目录记录（MySQL 注册表 → Pydantic → Milvus 向量记录）
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


class ApiCatalogPredecessorParamBinding(BaseModel):
    """前置接口到目标参数的绑定规则。"""

    target_param: str = Field(..., min_length=1, description="目标接口参数名")
    source_path: str = Field(..., min_length=1, description="前置接口响应取值路径")
    select_mode: Literal["single", "first", "user_select", "all"] = Field(
        "single",
        description="多值选择策略",
    )


class ApiCatalogPredecessorSpec(BaseModel):
    """单条前置依赖定义。"""

    predecessor_api_id: str = Field(..., min_length=1, description="前置接口 ID")
    required: bool = Field(True, description="是否必需前置接口")
    order: int = Field(100, description="前置执行顺序")
    param_bindings: list[ApiCatalogPredecessorParamBinding] = Field(
        default_factory=list,
        description="参数绑定规则",
    )


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


class ApiCatalogListViewFilterField(BaseModel):
    """列表筛选字段元数据。

    功能：
        该结构只描述“允许出现在首屏筛选区的字段”，不承载请求链路之外的展示策略，
        目的是把列表筛选入口稳定收敛到元数据白名单，避免每次都从 request_schema 全量推断。
    """

    field: str = Field(..., min_length=1, description="筛选字段名")
    label: str | None = Field(None, description="筛选字段展示名；为空时回退 request_schema 标题")


class ApiCatalogListViewTableField(BaseModel):
    """列表表格字段元数据。

    功能：
        该结构用于声明首屏表格列白名单和显示顺序。运行时只按这里的字段生成列，
        避免“接口返回字段越来越多，列表无限膨胀”的展示退化问题。
    """

    field: str = Field(..., min_length=1, description="表格字段名")
    title: str | None = Field(None, description="列表列标题；为空时回退 response_schema 标签")


class ApiCatalogListViewMeta(BaseModel):
    """列表视图元数据。

    功能：
        统一描述“列表筛选 + 表格列”的配置入口。若配置为空，运行时回退到历史自动推断逻辑。
    """

    filter_fields: list[ApiCatalogListViewFilterField] = Field(
        default_factory=list,
        description="列表筛选字段白名单（按配置顺序渲染）",
    )
    table_fields: list[ApiCatalogListViewTableField] = Field(
        default_factory=list,
        description="列表表格字段白名单（按配置顺序渲染）",
    )


class ApiCatalogDetailViewGroup(BaseModel):
    """详情卡分组定义。"""

    title: str = Field(..., min_length=1, description="分组标题")
    fields: list[str] = Field(default_factory=list, description="分组内字段名列表")


class ApiCatalogDetailViewMeta(BaseModel):
    """详情视图元数据。

    功能：
        定义详情页展示字段的准入规则与布局分组，遵循固定优先级：
        `exclude_fields > required_fields > display_fields`。

    Edge Cases:
        - `groups` 仅控制布局，不参与字段准入判定
        - 任何在 `exclude_fields` 中的字段都必须被强制剔除
    """

    display_fields: list[str] = Field(default_factory=list, description="默认可展示字段")
    required_fields: list[str] = Field(default_factory=list, description="必须展示字段")
    exclude_fields: list[str] = Field(default_factory=list, description="强制隐藏字段")
    groups: list[ApiCatalogDetailViewGroup] = Field(default_factory=list, description="详情分组配置")


class ApiCatalogSearchFilters(BaseModel):
    """Milvus 标量过滤器。"""

    domains: list[str] = Field(default_factory=list)
    envs: list[str] = Field(default_factory=list)
    statuses: list[str] = Field(default_factory=list)
    tag_names: list[str] = Field(default_factory=list)


class ApiCatalogFieldProfile(BaseModel):
    """接口字段原始画像。

    功能：
        在进入字段治理三表归一之前，先把接口 schema 中“这个字段在哪、长什么样”稳定保存下来。
        这样 resolver 可以复用统一的 raw 证据，而不是每次都从不同 schema 结构里重新猜。

    返回值约束：
        - `direction + location + json_path` 必须共同定位字段来源
        - `raw_field_type` 和 `raw_description` 允许为空，但字段名和路径不能为空
    """

    direction: Literal["request", "response"]
    location: Literal["queryParams", "body", "path", "response", "header"]
    field_name: str = Field(..., min_length=1, description="字段原始名称")
    json_path: str = Field(..., min_length=1, description="字段路径，如 body.roleId / data.records[].id")
    raw_field_type: str | None = Field(None, description="字段原始类型，如 string/int64/list<object>")
    raw_description: str | None = Field(None, description="字段原始描述，来自 schema/label/title")
    required: bool = Field(False, description="请求字段是否必填；响应字段默认 false")
    array_mode: bool = Field(False, description="字段是否来自数组元素或本身为数组")


class ApiCatalogEntry(BaseModel):
    """单条业务接口目录记录。

    功能：
        承接业务 MySQL 中 `ui_api_endpoints / ui_api_sources / ui_api_tags` 的联表结果，
        并转成网关内部统一的 API Catalog 契约，再投影为 Milvus `api_catalog` 的一条向量记录。
    """

    # ---------- 标识 ----------
    id: str = Field(..., description="接口唯一标识，如 biz_customer_list_v1")
    name: str = Field("", description="接口名称，来源于业务注册表 ui_api_endpoints.name")

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
    operation_safety: Literal["query", "list", "mutation"] = Field(
        "mutation",
        description="接口安全语义。query 表示可进入 /api-query，mutation 表示必须被阻断。",
    )
    requires_confirmation: bool = Field(
        False,
        description="是否属于高风险 mutation。GraphRAG 命中后需先进入确认分支。",
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
    list_view_meta: ApiCatalogListViewMeta = Field(
        default_factory=ApiCatalogListViewMeta,
        description="列表筛选与列表列的元数据白名单",
    )
    detail_view_meta: ApiCatalogDetailViewMeta = Field(
        default_factory=ApiCatalogDetailViewMeta,
        description="详情字段展示与分组元数据",
    )
    request_field_profiles: list[ApiCatalogFieldProfile] = Field(
        default_factory=list,
        description="请求侧原始字段画像，供字段治理与图同步复用",
    )
    response_field_profiles: list[ApiCatalogFieldProfile] = Field(
        default_factory=list,
        description="响应侧原始字段画像，供字段治理与图同步复用",
    )
    predecessors: list[ApiCatalogPredecessorSpec] = Field(
        default_factory=list,
        description="前置接口依赖定义（1:N）",
    )

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
