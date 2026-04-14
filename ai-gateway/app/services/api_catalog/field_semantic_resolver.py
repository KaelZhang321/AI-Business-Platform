"""字段语义解析器。

功能：
    把 `ApiCatalogEntry` 中的 raw 字段画像，统一解析成可建图的 `NormalizedFieldBinding`。
    这里承担的是“字段统一命名 + 类型统一 + 描述统一 + 标准分区注入”的职责，
    而不是直接写图；这样后续 Neo4j 同步、Stage 2 检索和 Stage 3 校验都能共享同一份事实。
"""

from __future__ import annotations

import logging
import re
from fnmatch import fnmatch

from app.services.api_catalog.graph_models import (
    NormalizedFieldBinding,
    SemanticFieldAliasRecord,
    SemanticFieldDictRecord,
    SemanticFieldValueMapRecord,
    SemanticGovernanceSnapshot,
)
from app.services.api_catalog.schema import ApiCatalogEntry, ApiCatalogFieldProfile, ParamSchema
from app.services.api_catalog.schema_utils import (
    describe_schema_type,
    extract_schema_description,
    resolve_schema_at_data_path,
    schema_is_array,
)
from app.services.api_catalog.semantic_field_repository import SemanticFieldRepository

logger = logging.getLogger(__name__)

_ALLOWED_GRAPH_ROLES = {"identifier", "locator", "bridge"}
_SCOPE_PRIORITY = {"alias": 0, "api": 1, "tag": 2, "domain": 3, "global": 4}
_COMMON_EXCLUDED_FIELDS = {
    "status",
    "type",
    "createtime",
    "create_time",
    "updatetime",
    "update_time",
    "page",
    "pageno",
    "page_no",
    "pagenum",
    "page_num",
    "pagesize",
    "page_size",
    "size",
    "limit",
    "offset",
    "sortfield",
    "sort_field",
    "sortorder",
    "sort_order",
    "total",
    "totalcount",
    "current",
    "currentpage",
}


class ApiFieldSemanticResolver:
    """GraphRAG 字段解析器。

    功能：
        用治理三表把接口字段收敛成统一字段画像，供图同步和后续路径校验复用。

    Args:
        repository: 可选的字段治理仓储。未显式传入时使用默认 MySQL 仓储。
    """

    def __init__(self, repository: SemanticFieldRepository | None = None) -> None:
        self._repository = repository or SemanticFieldRepository()

    async def resolve_bindings(
        self,
        entries: list[ApiCatalogEntry],
        *,
        governance_snapshot: SemanticGovernanceSnapshot | None = None,
    ) -> list[NormalizedFieldBinding]:
        """批量解析接口字段绑定。"""
        snapshot = governance_snapshot or await self._repository.load_active_rules()
        bindings: list[NormalizedFieldBinding] = []
        for entry in entries:
            bindings.extend(self.resolve_entry_bindings(entry, governance_snapshot=snapshot))
        return bindings

    async def load_governance_snapshot(self) -> SemanticGovernanceSnapshot:
        """加载当前字段治理快照。

        功能：
            全量重建索引时通常会连续处理大批接口。把快照加载显式开放出来，可以让 indexer
            先读一次治理三表，再把同一份只读快照复用到整轮任务里，避免重复访问 MySQL。
        """

        return await self._repository.load_active_rules()

    def resolve_entry_bindings(
        self,
        entry: ApiCatalogEntry,
        *,
        governance_snapshot: SemanticGovernanceSnapshot,
    ) -> list[NormalizedFieldBinding]:
        """解析单个接口的字段绑定。"""
        field_dict_map = governance_snapshot.field_dict_map()
        bindings: list[NormalizedFieldBinding] = []
        for profile in _collect_raw_profiles(entry):
            binding = _resolve_field_profile(entry, profile, governance_snapshot, field_dict_map)
            if binding is not None:
                bindings.append(binding)
        return bindings

    async def close(self) -> None:
        """关闭内部仓储连接。"""
        await self._repository.close()


def _collect_raw_profiles(entry: ApiCatalogEntry) -> list[ApiCatalogFieldProfile]:
    """收集接口原始字段画像。

    功能：
        正常路径优先复用 registry 已经提取好的字段画像；只有测试桩或历史调用方没有传入时，
        才临时回退到 schema 现算，避免未来同一入口出现两套字段提取口径。
    """
    if entry.request_field_profiles or entry.response_field_profiles:
        return [*entry.request_field_profiles, *entry.response_field_profiles]
    return [
        *_fallback_request_profiles(entry.method, entry.param_schema),
        *_fallback_response_profiles(entry.response_schema, entry.response_data_path, entry.field_labels),
    ]


def _resolve_field_profile(
    entry: ApiCatalogEntry,
    profile: ApiCatalogFieldProfile,
    snapshot: SemanticGovernanceSnapshot,
    field_dict_map: dict[str, SemanticFieldDictRecord],
) -> NormalizedFieldBinding | None:
    """解析单个 raw 字段。

    功能：
        这里的关键不是简单“找到一个别名就结束”，而是先按作用域命中语义键，再由主字典
        回填标准类型、标准描述和标准分区，确保图层消费到的是完整画像而不是半成品。
    """
    alias_record = _match_alias_record(entry, profile, snapshot.aliases)
    field_record = field_dict_map.get(alias_record.semantic_key) if alias_record is not None else None
    if field_record is None:
        field_record = _fallback_match_field_dict(entry, profile, snapshot.field_dicts)
    if field_record is None or not field_record.semantic_key:
        return None
    if not _allow_into_dependency_graph(field_record, profile):
        return None

    normalized_field_type, type_source = _resolve_field_type(profile, field_record)
    normalized_value_type = _resolve_value_type(profile, field_record)
    normalized_description, description_source = _resolve_description(profile, field_record)
    confidence = alias_record.confidence if alias_record is not None else 0.75

    # 这里不直接拒绝类型漂移，而是先降级置信度并把证据链保留下来。
    # 原因是第一期仍需要让治理台能看到“这个字段为什么被降权”，否则排查成本会转嫁到线上。
    if _is_high_risk_type_conflict(profile.raw_field_type, normalized_value_type):
        confidence = min(confidence, 0.35)

    value_mapping_rule = _summarize_value_mappings(
        entry,
        profile,
        field_record.semantic_key,
        snapshot.value_maps,
    )
    return NormalizedFieldBinding(
        api_id=entry.id,
        direction=profile.direction,
        location=profile.location,
        raw_field_name=profile.field_name,
        raw_field_type=profile.raw_field_type,
        raw_description=profile.raw_description,
        json_path=profile.json_path,
        semantic_key=field_record.semantic_key,
        entity_code=field_record.entity_code,
        canonical_name=field_record.canonical_name,
        normalized_label=field_record.label,
        normalized_field_type=normalized_field_type,
        normalized_value_type=normalized_value_type,
        normalized_description=normalized_description,
        category=field_record.category,
        business_domain=field_record.business_domain,
        display_domain_code=field_record.display_domain_code,
        display_domain_label=field_record.display_domain_label,
        display_section_code=field_record.display_section_code,
        display_section_label=field_record.display_section_label,
        required=profile.required,
        array_mode=profile.array_mode,
        value_mapping_rule=value_mapping_rule,
        confidence=confidence,
        source=alias_record.source if alias_record is not None else "field_dict",
        name_source=_build_name_source(alias_record),
        type_source=type_source,
        description_source=description_source,
        graph_role=field_record.graph_role,
        is_identifier=field_record.is_identifier,
        is_graph_enabled=field_record.is_graph_enabled,
    )


def _match_alias_record(
    entry: ApiCatalogEntry,
    profile: ApiCatalogFieldProfile,
    aliases: list[SemanticFieldAliasRecord],
) -> SemanticFieldAliasRecord | None:
    """按作用域优先级命中别名规则。"""
    normalized_field_name = _normalize_name(profile.field_name)
    candidates: list[SemanticFieldAliasRecord] = []
    for record in aliases:
        if not record.is_active:
            continue
        if _normalize_name(record.alias) != normalized_field_name:
            continue
        if not _scope_matches(entry, record):
            continue
        if not _direction_matches(profile.direction, record.direction):
            continue
        if not _location_matches(profile.location, record.location):
            continue
        if not _path_pattern_matches(profile.json_path, record.json_path_pattern):
            continue
        candidates.append(record)

    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda record: (
            _SCOPE_PRIORITY.get(record.scope_type, 99),
            int(record.priority),
            -float(record.confidence),
            record.semantic_key,
        ),
    )[0]


def _fallback_match_field_dict(
    entry: ApiCatalogEntry,
    profile: ApiCatalogFieldProfile,
    field_dicts: list[SemanticFieldDictRecord],
) -> SemanticFieldDictRecord | None:
    """在 alias 未命中时做最保守的字段字典回退匹配。

    功能：
        只有在“字段名唯一且业务上下文没有冲突”时才允许直接命中字典，避免 `id/name/status`
        这类高频字段被错误归到多个实体之一。
    """
    normalized_field_name = _normalize_name(profile.field_name)
    candidates = [
        record
        for record in field_dicts
        if record.is_active and normalized_field_name in _field_dict_match_keys(record)
    ]
    if not candidates:
        return None

    domain_matched = [
        record
        for record in candidates
        if _normalize_name(record.business_domain or record.display_domain_code or "") == _normalize_name(entry.domain)
    ]
    narrowed = domain_matched or candidates
    if len(narrowed) == 1:
        return narrowed[0]
    return None


def _allow_into_dependency_graph(record: SemanticFieldDictRecord, profile: ApiCatalogFieldProfile) -> bool:
    """判断字段是否允许进入依赖图。"""
    if not record.is_graph_enabled:
        return False
    if record.graph_role not in _ALLOWED_GRAPH_ROLES:
        return False

    normalized_field_name = _normalize_name(profile.field_name)
    # 对 `status/type/create_time/update_time/pageNum` 这类高频通用字段，第一期宁可少建边，
    # 也不要让它们把图污染成超级节点死结。
    if normalized_field_name in _COMMON_EXCLUDED_FIELDS and not record.is_identifier:
        return False
    return True


def _resolve_field_type(
    profile: ApiCatalogFieldProfile,
    record: SemanticFieldDictRecord,
) -> tuple[str, str]:
    """解析统一后的业务字段类型。"""
    if record.field_type:
        return record.field_type, "semantic_field_dict"
    return _infer_business_field_type(profile.raw_field_type), "raw_field_type"


def _resolve_value_type(profile: ApiCatalogFieldProfile, record: SemanticFieldDictRecord) -> str:
    """解析统一后的值结构类型。"""
    if record.value_type:
        return record.value_type
    return _infer_value_type(profile.raw_field_type)


def _resolve_description(
    profile: ApiCatalogFieldProfile,
    record: SemanticFieldDictRecord,
) -> tuple[str | None, str]:
    """解析统一后的字段描述。"""
    if record.description:
        return record.description, "semantic_field_dict"
    if profile.raw_description:
        return profile.raw_description, "raw_field_profile"
    return None, "inferred"


def _build_name_source(alias_record: SemanticFieldAliasRecord | None) -> str:
    """构建名称归一来源描述。"""
    if alias_record is None:
        return "field_dict_fallback"
    return f"semantic_field_alias:{alias_record.scope_type}"


def _summarize_value_mappings(
    entry: ApiCatalogEntry,
    profile: ApiCatalogFieldProfile,
    semantic_key: str,
    value_maps: list[SemanticFieldValueMapRecord],
) -> dict[str, object] | None:
    """提取值映射规则摘要。"""
    matched = [
        record
        for record in value_maps
        if record.is_active and record.semantic_key == semantic_key and _value_scope_matches(entry, profile, record)
    ]
    if not matched:
        return None
    ordered = sorted(
        matched,
        key=lambda record: (_SCOPE_PRIORITY.get(record.scope_type, 99), record.sort_order, -record.confidence),
    )
    return {
        "mapping_count": len(ordered),
        "standard_codes": [record.standard_code for record in ordered],
        "top_scope_type": ordered[0].scope_type,
        "top_scope_value": ordered[0].scope_value,
    }


def _scope_matches(entry: ApiCatalogEntry, record: SemanticFieldAliasRecord) -> bool:
    """判断 alias 作用域是否命中当前接口。"""
    scope_value = (record.scope_value or "").strip()
    if record.scope_type == "api":
        return scope_value == entry.id
    if record.scope_type == "tag":
        return scope_value == (entry.tag_name or "")
    if record.scope_type == "domain":
        return scope_value == entry.domain
    return scope_value in {"", "*", "global"}


def _value_scope_matches(
    entry: ApiCatalogEntry,
    profile: ApiCatalogFieldProfile,
    record: SemanticFieldValueMapRecord,
) -> bool:
    """判断值映射作用域是否命中当前接口。"""
    scope_value = (record.scope_value or "").strip()
    if record.scope_type == "alias":
        # `alias` 作用域只绑定字段名本身，目的是解决不同接口对同一枚举字段复用不同编码的问题。
        return _normalize_name(scope_value) == _normalize_name(profile.field_name)
    if record.scope_type == "api":
        return scope_value == entry.id
    if record.scope_type == "tag":
        return scope_value == (entry.tag_name or "")
    if record.scope_type == "domain":
        return scope_value == entry.domain
    return scope_value in {"", "*", "global"}


def _direction_matches(profile_direction: str, rule_direction: str) -> bool:
    """判断方向是否匹配。"""
    normalized_rule_direction = (rule_direction or "both").strip().lower()
    return normalized_rule_direction in {"both", "any", profile_direction}


def _location_matches(profile_location: str, rule_location: str) -> bool:
    """判断位置是否匹配。"""
    normalized_rule_location = (rule_location or "any").strip()
    return normalized_rule_location in {"", "any", profile_location}


def _path_pattern_matches(json_path: str, json_path_pattern: str | None) -> bool:
    """判断 JSONPath 模式是否命中。

    功能：
        治理规则里允许把 `data.records[*].id` 这种模式写得比 raw path 更宽松。
        这里统一把 `[*]` 退化成 `*` 做 glob 匹配，足够满足第一期的路径精度。
    """
    if not json_path_pattern:
        return True
    normalized_pattern = json_path_pattern.replace("[*]", "*")
    normalized_path = json_path.replace("[]", "")
    return fnmatch(normalized_path, normalized_pattern) or fnmatch(json_path, normalized_pattern)


def _field_dict_match_keys(record: SemanticFieldDictRecord) -> set[str]:
    """构造字段字典的兜底匹配键集合。"""
    keys = {
        _normalize_name(record.semantic_key.split(".")[-1] if record.semantic_key else ""),
        _normalize_name(record.standard_key or ""),
        _normalize_name(record.canonical_name or ""),
        _normalize_name(record.label or ""),
    }
    return {key for key in keys if key}


def _normalize_name(value: str) -> str:
    """统一字段名比较口径。"""
    return re.sub(r"[^a-z0-9]+", "", (value or "").strip().lower())


def _infer_business_field_type(raw_field_type: str | None) -> str:
    """从 raw 类型推断业务字段类型。"""
    normalized = (raw_field_type or "").strip().lower()
    if any(token in normalized for token in {"date", "time"}):
        return "date"
    if normalized in {"boolean", "bool"}:
        return "boolean"
    if normalized in {"integer", "int", "int32", "int64", "number", "float", "double"}:
        return "number"
    if normalized.startswith("list<") or normalized == "array":
        return "array"
    if normalized == "object":
        return "object"
    return "text"


def _infer_value_type(raw_field_type: str | None) -> str:
    """从 raw 类型推断值结构类型。"""
    normalized = (raw_field_type or "").strip().lower()
    if normalized.startswith("list<") or normalized == "array":
        return "array"
    if normalized == "object":
        return "object"
    if normalized in {"integer", "int", "int32", "int64"}:
        return "integer"
    if normalized in {"number", "float", "double"}:
        return "number"
    if any(token in normalized for token in {"date", "time"}):
        return "datetime"
    if normalized in {"boolean", "bool"}:
        return "boolean"
    return "string"


def _is_high_risk_type_conflict(raw_field_type: str | None, normalized_value_type: str) -> bool:
    """判断类型是否发生高风险冲突。"""
    inferred_raw_value_type = _infer_value_type(raw_field_type)
    if inferred_raw_value_type == normalized_value_type:
        return False
    numeric_group = {"integer", "number"}
    if {inferred_raw_value_type, normalized_value_type}.issubset(numeric_group):
        return False
    return True


def _fallback_request_profiles(method: str, param_schema: ParamSchema) -> list[ApiCatalogFieldProfile]:
    """在 entry 缺少 request profiles 时临时回退生成。"""
    location: str = "queryParams" if method.upper() == "GET" else "body"
    required_fields = set(param_schema.required)
    profiles: list[ApiCatalogFieldProfile] = []
    for field_name, field_schema in param_schema.properties.items():
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
                required=field_name in required_fields,
                array_mode=schema_is_array(field_schema),
            )
        )
    return profiles


def _fallback_response_profiles(
    response_schema: dict[str, object],
    response_data_path: str,
    field_labels: dict[str, str],
) -> list[ApiCatalogFieldProfile]:
    """在 entry 缺少 response profiles 时临时回退生成。"""
    data_schema, array_mode = resolve_schema_at_data_path(response_schema, response_data_path)
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
                json_path=f"{response_data_path}[].{field_name}" if array_mode else f"{response_data_path}.{field_name}",
                raw_field_type=describe_schema_type(field_schema),
                raw_description=extract_schema_description(field_schema, fallback_label=field_labels.get(field_name)),
                required=False,
                array_mode=array_mode or schema_is_array(field_schema),
            )
        )
    return profiles
