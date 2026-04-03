from __future__ import annotations

import aiomysql
import json
import logging
import re
from pathlib import Path
from typing import Any

import yaml

from app.core.config import settings
from app.services.api_catalog.schema import (
    ApiCatalogDetailHint,
    ApiCatalogEntry,
    ApiCatalogPaginationHint,
    ApiCatalogTemplateHint,
    ParamSchema,
)

logger = logging.getLogger(__name__)

_API_CATALOG_REGISTRY_SQL = """
SELECT
    e.id AS endpointId,
    e.tag_id AS tagId,
    t.name AS tagName,
    e.name AS endpointName,
    e.path AS path,
    e.method AS method,
    e.summary AS summary,
    CAST(e.request_schema AS CHAR) AS requestSchema,
    CAST(e.response_schema AS CHAR) AS responseSchema,
    CAST(e.sample_request AS CHAR) AS sampleRequest,
    CAST(e.sample_response AS CHAR) AS sampleResponse,
    e.status AS endpointStatus,
    s.id AS sourceId,
    s.code AS sourceCode,
    s.name AS sourceName,
    s.source_type AS sourceType,
    s.base_url AS baseUrl,
    s.doc_url AS docUrl,
    s.auth_type AS authType,
    CAST(s.auth_config AS CHAR) AS authConfig,
    CAST(s.default_headers AS CHAR) AS defaultHeaders,
    s.env AS env,
    s.status AS sourceStatus
FROM ui_api_endpoints e
LEFT JOIN ui_api_sources s ON e.source_id = s.id
LEFT JOIN ui_api_tags t ON e.tag_id = t.id
ORDER BY s.code, t.name, e.method, e.path
"""


class ApiCatalogSourceError(RuntimeError):
    """Raised when the registry source cannot be loaded."""


class ApiCatalogRegistrySource:
    """从权威元数据源构建 `ApiCatalogEntry` 列表。

    功能：
        统一承接 YAML、本地 overlay、ai-gateway 直连 MySQL 三类来源，产出可直接入库
        到 Milvus 的标准化目录记录。

    Edge Cases:
        - `ui_builder` 模式在切换后作为“严格直连 MySQL”兼容别名使用
        - `hybrid` 模式下 MySQL 不可用时允许回退到 overlay，保障本地开发与演示链路可用
        - SQL 里显式 `CAST(JSON AS CHAR)`，是为了消除不同 MySQL 驱动对 JSON 返回类型的差异
    """

    def __init__(self) -> None:
        self._pool: aiomysql.Pool | None = None

    async def load_entries(self, config_path: str | None = None) -> list[ApiCatalogEntry]:
        """按配置模式加载接口目录记录。

        Args:
            config_path: overlay YAML 路径；为空时读取默认 `config/api_catalog.yaml`。

        Returns:
            标准化后的 `ApiCatalogEntry` 列表，且始终附带 builtin 字典接口。

        Raises:
            ApiCatalogSourceError: 当 source mode 非法，或强制远端模式下元数据不可用。
        """
        source_mode = settings.api_catalog_source_mode.strip().lower()
        if source_mode not in {"yaml", "ui_builder", "hybrid"}:
            raise ApiCatalogSourceError(f"Unsupported api catalog source mode: {source_mode}")
        overlay_entries = _load_overlay_entries(config_path)

        if source_mode == "yaml":
            return _append_builtin_entries(overlay_entries)

        remote_entries: list[ApiCatalogEntry] = []
        try:
            remote_entries = await self._load_mysql_entries()
        except Exception as exc:
            if source_mode == "ui_builder":
                raise ApiCatalogSourceError(f"无法从 MySQL 加载注册表: {exc}") from exc
            logger.warning("Falling back to YAML api catalog source after MySQL load failed: %s", exc)

        if not remote_entries:
            return _append_builtin_entries(overlay_entries)

        return _append_builtin_entries(_merge_overlay_entries(remote_entries, overlay_entries))

    async def _load_mysql_entries(self) -> list[ApiCatalogEntry]:
        """从业务 MySQL 直连抽取接口目录元数据。

        功能：
            直接对齐设计稿里的 `ui_api_endpoints + ui_api_sources + ui_api_tags` 三表拍平逻辑，
            避免在网关和 business-server 之间再绕一层 REST 元数据代理。
        """
        rows = await self._fetch_mysql_rows(_API_CATALOG_REGISTRY_SQL)
        entries = [_build_entry_from_mysql_row(row) for row in rows]
        if not entries:
            raise ApiCatalogSourceError("MySQL metadata returned no endpoints")
        return _dedupe_by_signature(entries)

    async def _fetch_mysql_rows(self, sql: str) -> list[dict[str, Any]]:
        """执行注册表元数据 SQL，并返回字典行结果。"""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(sql)
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def _get_pool(self) -> aiomysql.Pool:
        """懒加载 API Catalog MySQL 连接池。"""
        if self._pool is None:
            self._pool = await aiomysql.create_pool(minsize=1, maxsize=5, **_build_ai_mysql_conn_params())
        return self._pool

    async def close(self) -> None:
        """释放内部连接池。"""
        if self._pool is not None:
            self._pool.close()
            await self._pool.wait_closed()
            self._pool = None


def _build_ai_mysql_conn_params() -> dict[str, str | int]:
    """从 `AI_MYSQL_*` 生成 API Catalog 直连配置。"""
    return {
        "host": settings.ai_mysql_host,
        "port": settings.ai_mysql_port,
        "user": settings.ai_mysql_user,
        "password": settings.ai_mysql_password,
        "db": settings.ai_mysql_database,
        "charset": "utf8mb4",
    }


def _build_entry_from_mysql_row(row: dict[str, Any]) -> ApiCatalogEntry:
    """把 SQL 联表结果转换成统一的目录对象。

    设计意图：
        通过一层 payload 适配复用 `_build_entry()`，让“SQL 主源”和“历史 REST 主源”
        共用同一套拍平与字段推断逻辑，减少后续演进时的分叉维护成本。
    """
    source_payload = {
        "id": row.get("sourceId"),
        "code": row.get("sourceCode"),
        "name": row.get("sourceName"),
        "sourceType": row.get("sourceType"),
        "baseUrl": row.get("baseUrl"),
        "docUrl": row.get("docUrl"),
        "authType": row.get("authType"),
        "authConfig": row.get("authConfig"),
        "defaultHeaders": row.get("defaultHeaders"),
        "env": row.get("env"),
        "status": row.get("sourceStatus"),
    }
    endpoint_payload = {
        "id": row.get("endpointId"),
        "tagId": row.get("tagId"),
        "tagName": row.get("tagName"),
        "name": row.get("endpointName"),
        "path": row.get("path"),
        "method": row.get("method"),
        "summary": row.get("summary"),
        "requestSchema": row.get("requestSchema"),
        "responseSchema": row.get("responseSchema"),
        "sampleRequest": row.get("sampleRequest"),
        "sampleResponse": row.get("sampleResponse"),
        "status": row.get("endpointStatus"),
    }
    return _build_entry(source_payload, endpoint_payload)


def _build_entry(
    source: dict[str, Any],
    endpoint: dict[str, Any],
    tag_name_by_id: dict[str, str] | None = None,
) -> ApiCatalogEntry:
    """把一条接口元数据拍平成 `ApiCatalogEntry`。

    Args:
        source: 接口源元数据，提供 domain/env/auth/base_url 等外围信息。
        endpoint: 单条接口定义，包含 path/schema/sample 等接口级信息。
        tag_name_by_id: 由 `/tags` 拉取到的显式标签映射。

    Returns:
        可直接入库 Milvus 的标准目录对象。
    """
    method = str(endpoint.get("method") or "GET").upper()
    path = str(endpoint.get("path") or "")
    name = str(endpoint.get("name") or "").strip()
    summary = str(endpoint.get("summary") or "").strip()

    request_schema = _safe_json_loads(endpoint.get("requestSchema"))
    response_schema = _safe_json_loads(endpoint.get("responseSchema"))
    sample_request = _safe_json_loads(endpoint.get("sampleRequest"))
    sample_response = _safe_json_loads(endpoint.get("sampleResponse"))

    auth_type = str(source.get("authType") or "").strip()
    auth_required = auth_type.lower() not in {"", "none", "public", "anonymous"}
    source_code = str(source.get("code") or "").strip()
    source_name = str(source.get("name") or "").strip()
    tag_name = _resolve_tag_name(endpoint, tag_name_by_id or {})

    return ApiCatalogEntry(
        id=str(endpoint.get("id") or f"{method}:{path}"),
        description=summary or name or f"{method} {path}",
        example_queries=_build_example_queries(name, summary),
        tags=_compact_list([tag_name, source_name, source_code, method]),
        domain=_normalize_domain(source_code or source_name or "generic"),
        env=str(source.get("env") or "shared"),
        status=_normalize_status(endpoint.get("status") or source.get("status") or "active"),
        tag_name=_normalize_tag_name(tag_name),
        business_intents=_infer_business_intents(name, summary, path),
        method=method,
        path=path,
        auth_required=auth_required,
        executor_config={
            "source_id": source.get("id"),
            "source_code": source_code,
            "source_name": source_name,
            "source_type": source.get("sourceType"),
            "base_url": source.get("baseUrl"),
            "doc_url": source.get("docUrl"),
            "auth_type": auth_type,
            "auth_config": _safe_json_loads(source.get("authConfig")),
            "default_headers": _safe_json_loads(source.get("defaultHeaders")),
        },
        security_rules={
            "auth_required": auth_required,
            "read_only": method == "GET",
            "source_status": source.get("status"),
            "endpoint_status": endpoint.get("status"),
            "enforcement": "delegated_to_business_server",
        },
        param_schema=_to_param_schema(request_schema),
        response_schema=response_schema,
        sample_request=sample_request,
        response_data_path=_infer_response_data_path(sample_response, response_schema),
        field_labels=_extract_field_labels(response_schema),
        ui_hint=_infer_ui_hint(summary, path, sample_response),
        detail_hint=ApiCatalogDetailHint(),
        pagination_hint=ApiCatalogPaginationHint(),
        template_hint=ApiCatalogTemplateHint(),
    )


def _merge_overlay_entries(remote_entries: list[ApiCatalogEntry], overlay_entries: list[ApiCatalogEntry]) -> list[ApiCatalogEntry]:
    overlay_by_signature = {(entry.method, entry.path): entry for entry in overlay_entries}
    merged: list[ApiCatalogEntry] = []
    for remote_entry in remote_entries:
        overlay = overlay_by_signature.get((remote_entry.method, remote_entry.path))
        if overlay is None:
            merged.append(remote_entry)
            continue
        merged.append(_merge_overlay(remote_entry, overlay))
    return merged


def _merge_overlay(remote_entry: ApiCatalogEntry, overlay_entry: ApiCatalogEntry) -> ApiCatalogEntry:
    """合并远端权威元数据与本地 overlay。

    设计意图：
        overlay 的职责是“补丁”，不是“覆盖整个远端对象”。因此只让用户显式声明的字段
        覆盖远端；其它字段继续继承 MySQL 主源提供的最新 schema 与运行时提示。
    """
    merged = overlay_entry.model_copy(deep=True)
    merged.domain = remote_entry.domain or overlay_entry.domain
    merged.env = remote_entry.env or overlay_entry.env
    merged.status = remote_entry.status or overlay_entry.status
    merged.tag_name = remote_entry.tag_name or overlay_entry.tag_name
    merged.auth_required = remote_entry.auth_required
    merged.executor_config = {**remote_entry.executor_config, **overlay_entry.executor_config}
    merged.security_rules = {**remote_entry.security_rules, **overlay_entry.security_rules}
    overlay_fields = set(overlay_entry.model_fields_set)

    if "description" not in overlay_fields:
        merged.description = remote_entry.description

    if "example_queries" in overlay_fields:
        merged.example_queries = _compact_list([*overlay_entry.example_queries, *remote_entry.example_queries])
    else:
        merged.example_queries = remote_entry.example_queries

    if "tags" in overlay_fields:
        merged.tags = _compact_list([*overlay_entry.tags, *remote_entry.tags])
    else:
        merged.tags = remote_entry.tags

    if "business_intents" in overlay_fields:
        merged.business_intents = _compact_list([*overlay_entry.business_intents, *remote_entry.business_intents])
    else:
        merged.business_intents = remote_entry.business_intents

    merged.param_schema = _merge_model_field(
        remote_entry.param_schema,
        overlay_entry.param_schema,
        explicit="param_schema" in overlay_fields,
    )
    merged.response_schema = (
        {**remote_entry.response_schema, **overlay_entry.response_schema}
        if "response_schema" in overlay_fields
        else remote_entry.response_schema
    )
    merged.sample_request = (
        overlay_entry.sample_request
        if "sample_request" in overlay_fields
        else remote_entry.sample_request
    )
    merged.response_data_path = (
        overlay_entry.response_data_path
        if "response_data_path" in overlay_fields
        else remote_entry.response_data_path
    )
    merged.field_labels = (
        {**remote_entry.field_labels, **overlay_entry.field_labels}
        if "field_labels" in overlay_fields
        else remote_entry.field_labels
    )
    merged.ui_hint = overlay_entry.ui_hint if "ui_hint" in overlay_fields else remote_entry.ui_hint
    merged.detail_hint = _merge_model_field(
        remote_entry.detail_hint,
        overlay_entry.detail_hint,
        explicit="detail_hint" in overlay_fields,
    )
    merged.pagination_hint = _merge_model_field(
        remote_entry.pagination_hint,
        overlay_entry.pagination_hint,
        explicit="pagination_hint" in overlay_fields,
    )
    merged.template_hint = _merge_model_field(
        remote_entry.template_hint,
        overlay_entry.template_hint,
        explicit="template_hint" in overlay_fields,
    )
    return merged


def _append_builtin_entries(entries: list[ApiCatalogEntry]) -> list[ApiCatalogEntry]:
    by_signature = {(entry.method, entry.path): entry for entry in entries}
    dict_entry = _build_system_dict_entry()
    by_signature.setdefault((dict_entry.method, dict_entry.path), dict_entry)
    return list(by_signature.values())


def _build_system_dict_entry() -> ApiCatalogEntry:
    """注册系统级万能字典接口。

    设计意图：
        字典项本质上是“高复用的枚举读取能力”，应以单条通用接口注册，
        再通过 `allowed_values` 约束可用字典编码，避免为每个下拉框膨胀一条 API。
    """
    allowed_values = ["customer_region", "customer_level", "industry", "contract_type"]
    return ApiCatalogEntry(
        id="system_dicts_v1",
        description="批量获取系统级字典项。用于生成表单下拉选项和枚举值映射。",
        example_queries=["获取客户等级字典", "查询客户区域下拉选项", "获取合同类型字典"],
        tags=["system", "dictionary", "options"],
        domain="system",
        env="shared",
        status="active",
        tag_name="dictionary",
        business_intents=["query_business_data"],
        method="GET",
        path="/api/system/dicts",
        auth_required=True,
        executor_config={
            "source_id": "builtin",
            "source_code": "system",
            "source_name": "System Builtins",
            "auth_type": "bearer",
        },
        security_rules={
            "auth_required": True,
            "read_only": True,
            "enforcement": "delegated_to_business_server",
        },
        param_schema=ParamSchema(
            type="object",
            properties={
                "types": {
                    "type": "string",
                    "description": "字典编码，多个用逗号分隔",
                    "allowed_values": allowed_values,
                }
            },
            required=["types"],
        ),
        response_schema={
            "type": "object",
            "properties": {
                "data": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "label": {"type": "string", "description": "显示文案"},
                            "value": {"type": "string", "description": "提交值"},
                            "type": {"type": "string", "description": "字典编码"},
                        },
                    },
                }
            },
        },
        sample_request={"types": "customer_region,customer_level"},
        response_data_path="data",
        field_labels={"label": "标签", "value": "值"},
        ui_hint="list",
        detail_hint=ApiCatalogDetailHint(),
        pagination_hint=ApiCatalogPaginationHint(),
        template_hint=ApiCatalogTemplateHint(),
    )


def _load_overlay_entries(config_path: str | None) -> list[ApiCatalogEntry]:
    path = Path(config_path or _default_overlay_path())
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as file:
        raw = yaml.safe_load(file) or {}
    return [ApiCatalogEntry(**item) for item in raw.get("apis", []) if isinstance(item, dict)]


def _default_overlay_path() -> str:
    return str(Path(__file__).resolve().parents[3] / "config" / "api_catalog.yaml")


def _dedupe_by_signature(entries: list[ApiCatalogEntry]) -> list[ApiCatalogEntry]:
    by_signature: dict[tuple[str, str], ApiCatalogEntry] = {}
    for entry in entries:
        by_signature[(entry.method, entry.path)] = entry
    return list(by_signature.values())


def _merge_model_field(remote_model: Any, overlay_model: Any, *, explicit: bool) -> Any:
    """按字段粒度合并 Pydantic 子模型。

    overlay 一旦显式声明某个复杂字段，通常只会改其中 1-2 个键。
    这里保留远端元数据剩余字段，避免因为 overlay 的局部补丁把整段 schema 或 hint 覆盖成默认值。
    """
    if not explicit:
        return remote_model
    remote_payload = remote_model.model_dump() if hasattr(remote_model, "model_dump") else dict(remote_model or {})
    overlay_fields = getattr(overlay_model, "model_fields_set", set())
    merged_payload = dict(remote_payload)
    for field_name in overlay_fields:
        merged_payload[field_name] = getattr(overlay_model, field_name)
    model_cls = type(remote_model)
    return model_cls(**merged_payload) if hasattr(model_cls, "model_validate") else merged_payload


def _normalize_domain(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")
    return normalized or "generic"


def _normalize_tag_name(value: str | None) -> str | None:
    if not value:
        return None
    # `tag_name` 直接参与标量过滤，不能因为团队使用中文标签就被归一化成空值。
    normalized = re.sub(r"[^\w]+", "_", value.strip().lower()).strip("_")
    return normalized or None


def _normalize_status(value: Any) -> str:
    normalized = str(value or "active").strip().lower()
    if normalized in {"active", "enabled", "online"}:
        return "active"
    if normalized in {"deprecated", "archived"}:
        return "deprecated"
    return "inactive"


def _build_example_queries(name: str, summary: str) -> list[str]:
    queries = []
    if summary:
        queries.append(summary)
    if name:
        queries.append(f"查询{name}")
    return _compact_list(queries)


def _resolve_tag_name(endpoint: dict[str, Any], tag_name_by_id: dict[str, str]) -> str | None:
    """解析接口标签名。

    优先级：
        1. endpoint 自带的 `tagName`
        2. 外部显式提供的 `tagId -> tagName` 映射

    注意：
        如果两者都缺失，返回 `None`，而不是把 `tagId` 当作可读标签名写入目录。
    """
    direct_tag_name = _first_non_empty(endpoint.get("tagName"))
    if direct_tag_name:
        return direct_tag_name

    tag_id = _first_non_empty(endpoint.get("tagId"))
    if not tag_id:
        return None

    resolved = tag_name_by_id.get(str(tag_id))
    if resolved:
        return resolved

    logger.debug("UI Builder endpoint tag could not be resolved: endpoint_id=%s tag_id=%s", endpoint.get("id"), tag_id)
    return None


def _infer_business_intents(name: str, summary: str, path: str) -> list[str]:
    haystack = f"{name} {summary} {path}".lower()
    if any(keyword in haystack for keyword in ("detail", "详情", "info", "profile")):
        return ["query_business_data", "query_detail_data"]
    return ["query_business_data"]


def _infer_response_data_path(sample_response: Any, response_schema: dict[str, Any]) -> str:
    if isinstance(sample_response, dict):
        if isinstance(sample_response.get("data"), dict):
            data = sample_response["data"]
            if isinstance(data.get("list"), list):
                return "data.list"
            if isinstance(data.get("records"), list):
                return "data.records"
            return "data"
        if isinstance(sample_response.get("list"), list):
            return "list"
        if isinstance(sample_response.get("records"), list):
            return "records"

    properties = response_schema.get("properties")
    if isinstance(properties, dict):
        data_property = properties.get("data")
        if isinstance(data_property, dict):
            data_props = data_property.get("properties")
            if isinstance(data_props, dict):
                if isinstance(data_props.get("list"), dict):
                    return "data.list"
                if isinstance(data_props.get("records"), dict):
                    return "data.records"
    return "data"


def _extract_field_labels(response_schema: dict[str, Any]) -> dict[str, str]:
    labels: dict[str, str] = {}
    candidates = _schema_property_candidates(response_schema)
    for name, schema in candidates.items():
        if not isinstance(schema, dict):
            continue
        label = schema.get("description") or schema.get("title")
        if isinstance(label, str) and label.strip():
            labels[name] = label.strip()
    return labels


def _schema_property_candidates(response_schema: dict[str, Any]) -> dict[str, Any]:
    properties = response_schema.get("properties")
    if not isinstance(properties, dict):
        return {}

    data_property = properties.get("data")
    if isinstance(data_property, dict):
        data_properties = data_property.get("properties")
        if isinstance(data_properties, dict):
            list_property = data_properties.get("list") or data_properties.get("records")
            if isinstance(list_property, dict):
                items = list_property.get("items")
                item_properties = items.get("properties") if isinstance(items, dict) else None
                if isinstance(item_properties, dict):
                    return item_properties
            return data_properties
    return properties


def _infer_ui_hint(summary: str, path: str, sample_response: Any) -> str:
    haystack = f"{summary} {path}".lower()
    if any(keyword in haystack for keyword in ("trend", "report", "chart", "统计", "趋势")):
        return "chart"
    if any(keyword in haystack for keyword in ("summary", "概览", "汇总")):
        return "metric"
    if isinstance(sample_response, dict):
        if isinstance(sample_response.get("data"), dict) and any(
            isinstance(sample_response["data"].get(key), list) for key in ("list", "records")
        ):
            return "table"
    return "table"


def _to_param_schema(value: dict[str, Any]) -> ParamSchema:
    if not isinstance(value, dict):
        return ParamSchema()
    if value.get("type") and value.get("properties") is not None:
        try:
            return ParamSchema(**value)
        except Exception:
            return ParamSchema()
    properties = value.get("properties")
    if isinstance(properties, dict):
        return ParamSchema(type="object", properties=properties, required=value.get("required") or [])
    return ParamSchema()


def _safe_json_loads(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _compact_list(values: list[Any]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text and text not in result:
            result.append(text)
    return result


def _first_non_empty(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
        if value not in (None, "") and not isinstance(value, str):
            return str(value)
    return None
