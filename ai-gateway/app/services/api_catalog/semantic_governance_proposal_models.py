"""字段治理提案内部模型。

功能：
    统一承接“规则快筛 + LLM 兜底”输出的提案数据结构，避免治理服务、写库仓储和任务状态
    在字段层面各自维护一套松散 dict，导致上线后难以追溯“某条规则为什么会被判定为待审”。
"""

from __future__ import annotations

from collections import defaultdict
from typing import Literal

from pydantic import BaseModel, Field


class SemanticDictProposal(BaseModel):
    """主字典提案。

    功能：
        描述一条 `semantic_field_dict` 候选规则，供离线治理批次落库。

    返回值约束：
        - `semantic_key` 必须是 `Entity.field` 结构
        - `review_status` 只能由治理服务判定，不允许路由层直接硬编码
    """

    semantic_key: str = Field(..., min_length=3)
    standard_key: str = Field(..., min_length=1)
    entity_code: str = Field(..., min_length=1)
    canonical_name: str = Field(..., min_length=1)
    label: str = Field(..., min_length=1)
    field_type: str = Field("text")
    value_type: str = Field("string")
    category: str = Field("business")
    display_domain_code: str | None = None
    display_domain_label: str | None = None
    display_section_code: str | None = None
    display_section_label: str | None = None
    graph_role: str = Field("none")
    is_identifier: bool = False
    is_graph_enabled: bool = True
    description: str | None = None
    risk_level: Literal["high", "low"] = "low"
    source: str = Field("rule_engine")
    confidence: float = Field(0.5, ge=0.0, le=1.0)
    review_status: Literal["pending", "approved", "rejected", "conflict_review"] = "pending"


class SemanticAliasProposal(BaseModel):
    """别名提案。"""

    semantic_key: str = Field(..., min_length=3)
    alias: str = Field(..., min_length=1)
    scope_type: str = Field("api")
    scope_value: str = Field("*")
    direction: str = Field("both")
    location: str = Field("any")
    json_path_pattern: str | None = None
    priority: int = 100
    source: str = Field("rule_engine")
    confidence: float = Field(0.5, ge=0.0, le=1.0)
    review_status: Literal["pending", "approved", "rejected", "conflict_review"] = "pending"


class SemanticValueMapProposal(BaseModel):
    """值域映射提案。"""

    semantic_key: str = Field(..., min_length=3)
    scope_type: str = Field("alias")
    scope_value: str = Field(..., min_length=1)
    raw_value: str = Field(..., min_length=1)
    raw_label: str | None = None
    standard_code: str = Field(..., min_length=1)
    standard_label: str = Field(..., min_length=1)
    sort_order: int = 0
    source: str = Field("rule_engine")
    confidence: float = Field(0.5, ge=0.0, le=1.0)
    review_status: Literal["pending", "approved", "rejected", "conflict_review"] = "pending"


class SemanticGovernanceProposalBatch(BaseModel):
    """单次治理批次提案集合。

    功能：
        聚合一个 run 内的字典、别名和值域提案，并携带质量指标，供 run 状态机更新。
    """

    dict_proposals: list[SemanticDictProposal] = Field(default_factory=list)
    alias_proposals: list[SemanticAliasProposal] = Field(default_factory=list)
    value_map_proposals: list[SemanticValueMapProposal] = Field(default_factory=list)
    total_fields: int = 0
    high_confidence_fields: int = 0
    pending_fields: int = 0
    rejected_fields: int = 0


class SemanticGovernancePersistSummary(BaseModel):
    """提案写库摘要。"""

    dict_written: int = 0
    alias_written: int = 0
    value_map_written: int = 0
    rejected_by_human_lock: int = 0
    conflict_review_marked: int = 0


class UiBlueprintSectionRule(BaseModel):
    """UI 分区规则。

    功能：
        承接 `ui_blueprint_dict` 的一条规则，约束字段默认应落入哪个展示分区。
    """

    display_domain_code: str
    display_domain_label: str | None = None
    display_section_code: str
    display_section_label: str | None = None
    typical_fields: list[str] = Field(default_factory=list)
    priority: int = 100
    is_active: bool = True


class UiBlueprintSnapshot(BaseModel):
    """UI 分区字典快照。"""

    rules: list[UiBlueprintSectionRule] = Field(default_factory=list)

    def by_domain(self) -> dict[str, list[UiBlueprintSectionRule]]:
        """按展示域聚合规则并按优先级排序。"""

        grouped: dict[str, list[UiBlueprintSectionRule]] = defaultdict(list)
        for rule in self.rules:
            if not rule.is_active:
                continue
            grouped[rule.display_domain_code].append(rule)
        return {
            domain: sorted(rules, key=lambda item: (item.priority, item.display_section_code))
            for domain, rules in grouped.items()
        }
