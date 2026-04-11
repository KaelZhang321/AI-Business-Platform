"""GraphRAG 内部强类型契约。

功能：
    为 GraphRAG 的字段治理、图同步、子图检索和缓存层提供统一的数据边界。
    这批模型的重点不是“把 dict 改成 class”本身，而是把后续多波次都会复用的
    业务事实固定下来，避免每个 service 都自行解释字段画像和图返回结构。

返回值约束：
    - `NormalizedFieldBinding` 是图同步唯一消费的字段绑定事实
    - `ApiCatalogSubgraphResult` 只保留子图摘要，不承载 Neo4j 原始响应
    - `GraphSyncImpactResult` 明确表达同步完成后的受影响 API 集

Edge Cases:
    - 字段标准分区允许为空；为空表示字段已归一但暂不参与自动分组
    - scope / direction / location 保留字符串兼容能力，避免历史治理表脏值直接把解析器打挂
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, computed_field


class SemanticFieldDictRecord(BaseModel):
    """标准字段语义字典记录。

    功能：
        承接 `semantic_field_dict` 主表的一行，表达“这个字段在系统里到底是什么”。

    返回值约束：
        - `semantic_key` 必须是图侧唯一主键
        - `graph_role + is_graph_enabled` 决定字段是否允许进入依赖图

    Edge Cases:
        - `display_*` 为空时，字段仍可参与名称/类型/描述归一，但不能用于自动分组
    """

    semantic_key: str
    standard_key: str | None = None
    entity_code: str | None = None
    canonical_name: str | None = None
    label: str | None = None
    field_type: str | None = None
    value_type: str | None = None
    category: str | None = None
    business_domain: str | None = None
    display_domain_code: str | None = None
    display_domain_label: str | None = None
    display_section_code: str | None = None
    display_section_label: str | None = None
    graph_role: str = "none"
    is_identifier: bool = False
    is_graph_enabled: bool = True
    value_schema: dict[str, Any] | None = None
    description: str | None = None
    is_active: bool = True

    @computed_field(return_type=str | None)
    @property
    def display_partition_key(self) -> str | None:
        """派生字段主分区键。

        功能：
            运行时统一使用 `domain.section` 做卡片聚合键，避免每层 UI 都各自拼接一次。
        """
        if not self.display_domain_code or not self.display_section_code:
            return None
        return f"{self.display_domain_code}.{self.display_section_code}"


class SemanticFieldAliasRecord(BaseModel):
    """字段别名映射记录。"""

    semantic_key: str
    alias: str
    scope_type: str = "global"
    scope_value: str = "*"
    direction: str = "both"
    location: str = "any"
    json_path_pattern: str | None = None
    source: str = "manual"
    confidence: float = Field(1.0, ge=0.0, le=1.0)
    priority: int = 100
    is_active: bool = True


class SemanticFieldValueMapRecord(BaseModel):
    """字段标准值映射记录。"""

    semantic_key: str
    scope_type: str = "global"
    scope_value: str = "*"
    standard_code: str
    standard_label: str
    raw_value: str
    raw_label: str | None = None
    sort_order: int = 0
    source: str = "manual"
    confidence: float = Field(1.0, ge=0.0, le=1.0)
    is_active: bool = True


class SemanticGovernanceSnapshot(BaseModel):
    """字段治理三表的活动快照。

    功能：
        把 MySQL 三表拍平为一次可复用的只读快照，避免 resolver 在同一轮解析中反复查库。
    """

    field_dicts: list[SemanticFieldDictRecord] = Field(default_factory=list)
    aliases: list[SemanticFieldAliasRecord] = Field(default_factory=list)
    value_maps: list[SemanticFieldValueMapRecord] = Field(default_factory=list)
    loaded_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def field_dict_map(self) -> dict[str, SemanticFieldDictRecord]:
        """按 `semantic_key` 快速索引主表记录。"""
        return {record.semantic_key: record for record in self.field_dicts if record.is_active}


class NormalizedFieldBinding(BaseModel):
    """建图前的统一字段绑定事实。

    功能：
        把某个接口里的 raw 字段，收敛成后续图同步可直接消费的标准语义对象。

    返回值约束：
        - `semantic_key` 必须已完成统一命名
        - `normalized_field_type/value_type/description` 必须可解释其来源
        - `display_*` 为空时只表示不能自动分组，不影响字段已被归一

    Edge Cases:
        - `array_mode=true` 但 `required=false` 是合法状态，常见于列表筛选或响应数组字段
        - `confidence` 允许因为类型冲突降级，但不能超出 0-1 区间
    """

    api_id: str
    direction: Literal["request", "response"]
    location: Literal["queryParams", "body", "path", "response", "header"]
    raw_field_name: str
    raw_field_type: str | None = None
    raw_description: str | None = None
    json_path: str
    semantic_key: str
    normalized_field_type: str
    normalized_value_type: str
    normalized_description: str | None = None
    display_domain_code: str | None = None
    display_domain_label: str | None = None
    display_section_code: str | None = None
    display_section_label: str | None = None
    required: bool = False
    array_mode: bool = False
    value_mapping_rule: dict[str, Any] | None = None
    confidence: float = Field(1.0, ge=0.0, le=1.0)
    source: str = "inferred"
    name_source: str = "inferred"
    type_source: str = "inferred"
    description_source: str = "inferred"
    graph_role: str = "none"
    is_identifier: bool = False
    is_graph_enabled: bool = True

    @computed_field(return_type=str | None)
    @property
    def display_partition_key(self) -> str | None:
        """派生字段标准分区键。"""
        if not self.display_domain_code or not self.display_section_code:
            return None
        return f"{self.display_domain_code}.{self.display_section_code}"


class GraphFieldPath(BaseModel):
    """字段级图路径摘要。"""

    consumer_api_id: str
    producer_api_id: str
    semantic_key: str
    source_extract_path: str
    target_inject_path: str
    confidence: float = Field(1.0, ge=0.0, le=1.0)


class ApiCatalogSubgraphResult(BaseModel):
    """Stage 2 输出的候选子图摘要。"""

    anchor_api_ids: list[str] = Field(default_factory=list)
    support_api_ids: list[str] = Field(default_factory=list)
    field_paths: list[GraphFieldPath] = Field(default_factory=list)
    graph_degraded: bool = False
    degraded_reason: str | None = None


class GraphCacheHitResult(BaseModel):
    """缓存读取结果。"""

    key: str
    hit: bool = False
    subgraph: ApiCatalogSubgraphResult | None = None


class GraphValidationCacheEntry(BaseModel):
    """字段路径校验缓存记录。"""

    key: str
    is_valid: bool
    payload: dict[str, Any] = Field(default_factory=dict)


class GraphSyncImpactResult(BaseModel):
    """图同步影响面摘要。"""

    api_id: str
    impacted_api_ids: list[str] = Field(default_factory=list)
    sync_run_id: str
    metadata_version: str | None = None


class GraphCacheInvalidationRequest(BaseModel):
    """图缓存失效请求。

    功能：
        只允许按受影响 API 定向驱逐缓存，避免图版本全局推进引发缓存雪崩。
    """

    impacted_api_ids: list[str] = Field(default_factory=list)
    scopes: list[Literal["subgraph", "validate", "field_binding"]] = Field(
        default_factory=lambda: ["subgraph", "validate", "field_binding"]
    )
