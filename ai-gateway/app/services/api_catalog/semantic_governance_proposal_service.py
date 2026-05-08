"""字段治理提案生成服务。

功能：
    根据接口字段画像生成治理提案，覆盖“稳态快筛 + 异常字段兜底提案”两类路径。
    该服务只负责提案生成，不直接执行发布切流，保证控制面职责边界清晰。
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from app.models.schemas.catalog_governance import SemanticCurationPhase
from app.services.api_catalog.graph_models import SemanticGovernanceSnapshot
from app.services.api_catalog.schema import ApiCatalogEntry, ApiCatalogFieldProfile
from app.services.api_catalog.schema_utils import (
    describe_schema_type,
    extract_schema_description,
    resolve_schema_at_data_path,
    schema_is_array,
)
from app.services.api_catalog.semantic_governance_proposal_models import (
    SemanticAliasProposal,
    SemanticDictProposal,
    SemanticGovernanceProposalBatch,
    SemanticValueMapProposal,
    UiBlueprintSectionRule,
)
from app.services.api_catalog.ui_blueprint_repository import UiBlueprintRepository

_COMMON_NOISE_FIELD_NAMES = {
    "page",
    "pageno",
    "pagenum",
    "pagesize",
    "page_size",
    "page_no",
    "page_num",
    "limit",
    "offset",
    "sortfield",
    "sortorder",
    "createtime",
    "update_time",
    "updatetime",
    "traceid",
    "token",
    "sign",
}
_AUTO_SECTION_BY_CATEGORY = {
    "business": ("basic_info", "基本信息"),
    "pagination": ("pagination", "分页参数"),
    "system": ("system", "系统参数"),
    "audit": ("audit", "审计信息"),
}


class SemanticGovernanceProposalService:
    """字段治理提案生成服务。

    功能：
        把接口字段转换为 `dict/alias/value_map` 三表提案，并输出 run 指标统计，供状态机判定
        是否进入 `PROPOSED` 或 `REVIEW_PENDING`。

    Args:
        auto_approve_confidence: 低风险字段达到该置信度时自动标记为 `approved`。
    """

    def __init__(
        self,
        *,
        auto_approve_confidence: float = 0.9,
        ui_blueprint_repository: UiBlueprintRepository | None = None,
    ) -> None:
        self._auto_approve_confidence = auto_approve_confidence
        self._ui_blueprint_repository = ui_blueprint_repository or UiBlueprintRepository()

    async def close(self) -> None:
        """释放内部仓储资源。"""

        await self._ui_blueprint_repository.close()

    async def build_batch(
        self,
        *,
        entries: list[ApiCatalogEntry],
        phase: SemanticCurationPhase,
        governance_snapshot: SemanticGovernanceSnapshot,
    ) -> SemanticGovernanceProposalBatch:
        """构建治理提案批次。

        功能：
            `Plan B` 与 `Plan C` 的核心差异在“字段来源范围”，而不是提案结构本身。
            因此这里统一输出标准提案批次，调用方只需决定喂入的接口集合即可。

        Args:
            entries: 本批需要治理的接口集合。
            phase: 当前治理阶段（C 冷启动 / B 稳态）。
            governance_snapshot: 当前线上生效的治理快照，用于快筛与去重。

        Returns:
            可直接写入三表的提案批次。
        """

        alias_index = _build_alias_index(governance_snapshot)
        dict_index = {record.semantic_key: record for record in governance_snapshot.field_dicts if record.is_active}
        ui_blueprint_snapshot = await self._ui_blueprint_repository.load_snapshot()
        blueprint_rules_by_domain = ui_blueprint_snapshot.by_domain()

        batch = SemanticGovernanceProposalBatch()
        emitted_alias_keys: set[tuple[str, str, str, str, str, str]] = set()
        emitted_dict_keys: set[str] = set()
        emitted_value_keys: set[tuple[str, str, str, str]] = set()

        # 1) 冷启动与稳态都按“接口 -> 字段”展开，这样 run 指标和人工审核证据保持同一口径。
        for entry in entries:
            profiles = _collect_profiles(entry)
            for profile in profiles:
                normalized_name = _normalize_name(profile.field_name)
                if not normalized_name:
                    continue
                batch.total_fields += 1

                # 2) 命中现有别名时走快筛：只补齐 API 级作用域，不重复制造新语义键。
                existing_semantic_key = _resolve_existing_semantic_key(entry, profile, alias_index)
                if existing_semantic_key:
                    alias_proposal = _build_alias_extension_proposal(
                        entry=entry,
                        profile=profile,
                        semantic_key=existing_semantic_key,
                        confidence=0.98,
                        review_status="approved",
                    )
                    alias_key = _alias_dedup_key(alias_proposal)
                    if alias_key not in emitted_alias_keys:
                        emitted_alias_keys.add(alias_key)
                        batch.alias_proposals.append(alias_proposal)
                    batch.high_confidence_fields += 1
                    continue

                # 3) 未命中规则时进入兜底提案：生成主字典 + 别名 + 枚举值映射。
                dict_proposal = _build_dict_proposal(
                    entry=entry,
                    profile=profile,
                    phase=phase,
                    dict_index=dict_index,
                    blueprint_rules_by_domain=blueprint_rules_by_domain,
                )
                dict_proposal.review_status = _decide_review_status(
                    confidence=dict_proposal.confidence,
                    risk_level=dict_proposal.risk_level,
                    auto_approve_confidence=self._auto_approve_confidence,
                )
                dict_key = dict_proposal.semantic_key
                if dict_key not in emitted_dict_keys:
                    emitted_dict_keys.add(dict_key)
                    batch.dict_proposals.append(dict_proposal)

                alias_proposal = _build_alias_extension_proposal(
                    entry=entry,
                    profile=profile,
                    semantic_key=dict_proposal.semantic_key,
                    confidence=dict_proposal.confidence,
                    review_status=dict_proposal.review_status,
                )
                alias_key = _alias_dedup_key(alias_proposal)
                if alias_key not in emitted_alias_keys:
                    emitted_alias_keys.add(alias_key)
                    batch.alias_proposals.append(alias_proposal)

                for value_proposal in _extract_value_map_proposals(
                    profile=profile, semantic_key=dict_proposal.semantic_key
                ):
                    value_key = _value_dedup_key(value_proposal)
                    if value_key in emitted_value_keys:
                        continue
                    emitted_value_keys.add(value_key)
                    # 枚举值映射和字段主体保持同一审核状态，避免出现“字段待审但值映射已上线”的割裂态。
                    value_proposal.review_status = dict_proposal.review_status
                    batch.value_map_proposals.append(value_proposal)

                if dict_proposal.review_status == "approved":
                    batch.high_confidence_fields += 1
                elif dict_proposal.review_status in {"pending", "conflict_review"}:
                    batch.pending_fields += 1
                else:
                    batch.rejected_fields += 1
        return batch


def _collect_profiles(entry: ApiCatalogEntry) -> list[ApiCatalogFieldProfile]:
    """收集字段画像。

    功能：
        生产环境里绝大多数条目会提前拍平 profile；这里只在 profile 缺失时回退 schema 解析，
        保证治理链路对历史数据也可运行。
    """

    if entry.request_field_profiles or entry.response_field_profiles:
        return [*entry.request_field_profiles, *entry.response_field_profiles]
    return [
        *_fallback_request_profiles(entry),
        *_fallback_response_profiles(entry),
    ]


def _build_alias_index(snapshot: SemanticGovernanceSnapshot) -> dict[tuple[str, str], list[tuple[str, str]]]:
    """构建 alias 反向索引。"""

    grouped: dict[tuple[str, str], list[tuple[str, str]]] = defaultdict(list)
    for record in snapshot.aliases:
        if not record.is_active:
            continue
        key = (_normalize_name(record.alias), record.direction or "both")
        grouped[key].append((record.semantic_key, record.scope_type))
        grouped[(key[0], "both")].append((record.semantic_key, record.scope_type))
    return grouped


def _resolve_existing_semantic_key(
    entry: ApiCatalogEntry,
    profile: ApiCatalogFieldProfile,
    alias_index: dict[tuple[str, str], list[tuple[str, str]]],
) -> str | None:
    """解析字段是否已命中现有语义键。"""

    candidates = alias_index.get((_normalize_name(profile.field_name), profile.direction), [])
    if not candidates:
        candidates = alias_index.get((_normalize_name(profile.field_name), "both"), [])
    if not candidates:
        return None
    # 这里优先保留 API 级作用域命中的 semantic_key，防止跨域同名字段被 global 规则误吸附。
    scope_rank = {"api": 0, "tag": 1, "domain": 2, "global": 3}
    ordered = sorted(candidates, key=lambda item: scope_rank.get(item[1], 99))
    return ordered[0][0]


def _build_dict_proposal(
    *,
    entry: ApiCatalogEntry,
    profile: ApiCatalogFieldProfile,
    phase: SemanticCurationPhase,
    dict_index: dict[str, Any],
    blueprint_rules_by_domain: dict[str, list[UiBlueprintSectionRule]],
) -> SemanticDictProposal:
    """构建主字典提案。"""

    category = _infer_category(profile.field_name, profile.raw_description)
    entity_code = _to_entity_code(entry.domain)
    canonical_name = _to_canonical_name(profile.field_name)
    semantic_key = f"{entity_code}.{canonical_name}"
    if semantic_key in dict_index:
        existing = dict_index[semantic_key]
        field_type = existing.field_type or _infer_field_type(profile.raw_field_type)
        value_type = existing.value_type or _infer_value_type(profile.raw_field_type)
        label = existing.label or (profile.raw_description or profile.field_name)
        description = existing.description or profile.raw_description
    else:
        field_type = _infer_field_type(profile.raw_field_type)
        value_type = _infer_value_type(profile.raw_field_type)
        label = profile.raw_description or profile.field_name
        description = profile.raw_description

    is_identifier = canonical_name.endswith("_id") or canonical_name == "id"
    graph_role = "identifier" if is_identifier else "locator"
    if category != "business":
        graph_role = "none"
    is_graph_enabled = category == "business"
    risk_level = (
        "high" if is_identifier or (is_graph_enabled and graph_role in {"identifier", "locator", "bridge"}) else "low"
    )

    confidence = _infer_confidence(category=category, phase=phase, profile=profile)
    default_domain_code = entry.domain or "generic"
    default_domain_label = entry.tag_name or entry.domain or "通用分区"
    section_code, section_label = _AUTO_SECTION_BY_CATEGORY.get(category, _AUTO_SECTION_BY_CATEGORY["business"])
    chosen_domain_code, chosen_domain_label, chosen_section_code, chosen_section_label = _resolve_ui_partition(
        domain_code=default_domain_code,
        domain_label=default_domain_label,
        canonical_name=canonical_name,
        category=category,
        fallback_section_code=section_code,
        fallback_section_label=section_label,
        blueprint_rules_by_domain=blueprint_rules_by_domain,
    )
    return SemanticDictProposal(
        semantic_key=semantic_key,
        standard_key=canonical_name,
        entity_code=entity_code,
        canonical_name=canonical_name,
        label=label,
        field_type=field_type,
        value_type=value_type,
        category=category,
        display_domain_code=chosen_domain_code,
        display_domain_label=chosen_domain_label,
        display_section_code=chosen_section_code,
        display_section_label=chosen_section_label,
        graph_role=graph_role,
        is_identifier=is_identifier,
        is_graph_enabled=is_graph_enabled,
        description=description,
        risk_level=risk_level,
        source="llm_inferred" if phase == SemanticCurationPhase.PLAN_C else "rule_engine",
        confidence=confidence,
        review_status="pending",
    )


def _build_alias_extension_proposal(
    *,
    entry: ApiCatalogEntry,
    profile: ApiCatalogFieldProfile,
    semantic_key: str,
    confidence: float,
    review_status: str,
) -> SemanticAliasProposal:
    """构建别名提案。"""

    return SemanticAliasProposal(
        semantic_key=semantic_key,
        alias=profile.field_name,
        scope_type="api",
        scope_value=entry.id,
        direction=profile.direction,
        location=profile.location,
        json_path_pattern=profile.json_path,
        priority=10,
        source="rule_engine",
        confidence=confidence,
        review_status=review_status,
    )


def _extract_value_map_proposals(
    *, profile: ApiCatalogFieldProfile, semantic_key: str
) -> list[SemanticValueMapProposal]:
    """从字段描述中提取枚举值映射提案。"""

    if not profile.raw_description:
        return []
    segments = re.split(r"[，,；;]+", profile.raw_description)
    proposals: list[SemanticValueMapProposal] = []
    for segment in segments:
        matched = re.search(r"(?P<raw>[A-Za-z0-9_-]+)\s*[:：=-]\s*(?P<label>[^,，;；\s]+)", segment.strip())
        if not matched:
            continue
        raw_value = matched.group("raw").strip()
        standard_label = matched.group("label").strip()
        if not raw_value or not standard_label:
            continue
        proposals.append(
            SemanticValueMapProposal(
                semantic_key=semantic_key,
                scope_type="alias",
                scope_value=profile.field_name,
                raw_value=raw_value,
                raw_label=standard_label,
                standard_code=_to_standard_code(standard_label, raw_value),
                standard_label=standard_label,
                sort_order=len(proposals),
                source="rule_engine",
                confidence=0.9,
                review_status="pending",
            )
        )
    return proposals


def _infer_category(field_name: str, description: str | None) -> str:
    normalized_name = _normalize_name(field_name)
    normalized_description = _normalize_name(description or "")
    if normalized_name in _COMMON_NOISE_FIELD_NAMES or any(
        token in normalized_name for token in {"page", "limit", "offset", "sort"}
    ):
        return "pagination"
    if any(token in normalized_name for token in {"create", "update", "trace", "token", "sign"}):
        if "create" in normalized_name or "update" in normalized_name:
            return "audit"
        return "system"
    if "审计" in (description or "") or "更新时间" in (description or ""):
        return "audit"
    if "签名" in (description or "") or "链路" in (description or ""):
        return "system"
    if "status" in normalized_name and "分页" in normalized_description:
        return "pagination"
    return "business"


def _infer_confidence(*, category: str, phase: SemanticCurationPhase, profile: ApiCatalogFieldProfile) -> float:
    if category != "business":
        return 0.92
    if phase == SemanticCurationPhase.PLAN_C:
        # 冷启动阶段允许更保守，优先把疑似字段沉淀成待审提案，不盲目自动放行。
        return 0.72 if profile.raw_description else 0.62
    return 0.82 if profile.raw_description else 0.7


def _decide_review_status(*, confidence: float, risk_level: str, auto_approve_confidence: float) -> str:
    if risk_level == "high":
        return "pending"
    if confidence >= auto_approve_confidence:
        return "approved"
    return "pending"


def _to_entity_code(domain: str | None) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", " ", (domain or "generic")).strip()
    if not normalized:
        return "Generic"
    return "".join(token.capitalize() for token in normalized.split()) or "Generic"


def _to_canonical_name(field_name: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", field_name or "")
    if not words:
        return "field"
    tokens: list[str] = []
    for word in words:
        snake_split = re.findall(r"[A-Z]?[a-z]+|[0-9]+|[A-Z]+(?![a-z])", word)
        if snake_split:
            tokens.extend(part.lower() for part in snake_split)
        else:
            tokens.append(word.lower())
    return "_".join(token for token in tokens if token) or "field"


def _to_standard_code(label: str, raw_value: str) -> str:
    if "男" in label:
        return "male"
    if "女" in label:
        return "female"
    if "启用" in label or "正常" in label:
        return "active"
    if "禁用" in label or "停用" in label:
        return "inactive"

    text = _normalize_name(label)
    if text in {"male", "man", "nan", "boy"}:
        return "male"
    if text in {"female", "woman", "nv", "girl"}:
        return "female"
    if text in {"enable", "enabled", "active", "qi", "zhengchang"}:
        return "active"
    if text in {"disable", "disabled", "inactive", "tingyong"}:
        return "inactive"
    return _normalize_name(label) or _normalize_name(raw_value) or "unknown"


def _alias_dedup_key(proposal: SemanticAliasProposal) -> tuple[str, str, str, str, str, str]:
    return (
        proposal.semantic_key,
        proposal.alias,
        proposal.scope_type,
        proposal.scope_value,
        proposal.direction,
        proposal.location,
    )


def _value_dedup_key(proposal: SemanticValueMapProposal) -> tuple[str, str, str, str]:
    return (
        proposal.semantic_key,
        proposal.scope_type,
        proposal.scope_value,
        proposal.raw_value,
    )


def _infer_field_type(raw_field_type: str | None) -> str:
    normalized = (raw_field_type or "").strip().lower()
    if any(token in normalized for token in {"date", "time"}):
        return "date"
    if normalized in {"int", "integer", "int32", "int64", "number", "float", "double"}:
        return "number"
    if normalized in {"bool", "boolean"}:
        return "boolean"
    if normalized.startswith("list<") or normalized == "array":
        return "array"
    if normalized == "object":
        return "object"
    return "text"


def _infer_value_type(raw_field_type: str | None) -> str:
    normalized = (raw_field_type or "").strip().lower()
    if normalized.startswith("list<") or normalized == "array":
        return "array"
    if normalized == "object":
        return "object"
    if normalized in {"int", "integer", "int32", "int64"}:
        return "integer"
    if normalized in {"number", "float", "double"}:
        return "number"
    if normalized in {"bool", "boolean"}:
        return "boolean"
    if any(token in normalized for token in {"date", "time"}):
        return "datetime"
    return "string"


def _normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").strip().lower())


def _resolve_ui_partition(
    *,
    domain_code: str,
    domain_label: str | None,
    canonical_name: str,
    category: str,
    fallback_section_code: str,
    fallback_section_label: str,
    blueprint_rules_by_domain: dict[str, list[UiBlueprintSectionRule]],
) -> tuple[str, str | None, str, str]:
    """按 ui_blueprint_dict 规则解析默认展示分区。"""

    rules = blueprint_rules_by_domain.get(domain_code) or []
    if not rules:
        return domain_code, domain_label, fallback_section_code, fallback_section_label

    normalized_canonical = _normalize_name(canonical_name)
    normalized_tokens = {normalized_canonical, _normalize_name(canonical_name.replace("_", ""))}
    matched_rule = None
    for rule in rules:
        # 1) 优先按 typical_fields 命中，确保“字段级标准分区”由字典主导，不靠启发式猜测。
        if any(_normalize_name(field) in normalized_tokens for field in rule.typical_fields):
            matched_rule = rule
            break
    if matched_rule is None:
        # 2) 未命中典型字段时，降级到分类约束：系统字段优先 hidden/audit 分区，业务字段取该域首条规则。
        if category in {"system", "audit"}:
            for rule in rules:
                section_name = _normalize_name(rule.display_section_code)
                if section_name in {"hiddenkeys", "audittrail", "system", "audit"}:
                    matched_rule = rule
                    break
        matched_rule = matched_rule or rules[0]
    return (
        matched_rule.display_domain_code,
        matched_rule.display_domain_label or domain_label,
        matched_rule.display_section_code,
        matched_rule.display_section_label or fallback_section_label,
    )


def _fallback_request_profiles(entry: ApiCatalogEntry) -> list[ApiCatalogFieldProfile]:
    location = "queryParams" if entry.method == "GET" else "body"
    required = set(entry.param_schema.required)
    profiles: list[ApiCatalogFieldProfile] = []
    for field_name, field_schema in entry.param_schema.properties.items():
        if not isinstance(field_schema, dict):
            continue
        profiles.append(
            ApiCatalogFieldProfile(
                direction="request",
                location=location,
                field_name=field_name,
                json_path=f"{location}.{field_name}",
                raw_field_type=describe_schema_type(field_schema),
                raw_description=extract_schema_description(field_schema),
                required=field_name in required,
                array_mode=schema_is_array(field_schema),
            )
        )
    return profiles


def _fallback_response_profiles(entry: ApiCatalogEntry) -> list[ApiCatalogFieldProfile]:
    data_schema, array_mode = resolve_schema_at_data_path(entry.response_schema, entry.response_data_path)
    properties = data_schema.get("properties") if isinstance(data_schema, dict) else None
    if not isinstance(properties, dict):
        return []
    profiles: list[ApiCatalogFieldProfile] = []
    for field_name, field_schema in properties.items():
        if not isinstance(field_schema, dict):
            continue
        profiles.append(
            ApiCatalogFieldProfile(
                direction="response",
                location="response",
                field_name=field_name,
                json_path=f"{entry.response_data_path}[].{field_name}"
                if array_mode
                else f"{entry.response_data_path}.{field_name}",
                raw_field_type=describe_schema_type(field_schema),
                raw_description=extract_schema_description(
                    field_schema, fallback_label=entry.field_labels.get(field_name)
                ),
                required=False,
                array_mode=array_mode or schema_is_array(field_schema),
            )
        )
    return profiles
