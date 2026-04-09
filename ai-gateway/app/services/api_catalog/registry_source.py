from __future__ import annotations

import aiomysql
import json
import logging
import re
from typing import Any

from app.core.config import settings
from app.services.api_catalog.schema import (
    ApiCatalogDetailHint,
    ApiCatalogEntry,
    ApiCatalogPaginationHint,
    ApiCatalogTemplateHint,
    ParamSchema,
)

logger = logging.getLogger(__name__)

_API_CATALOG_REGISTRY_SELECT_SQL = """
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
    e.operation_safety AS operationSafety,
    e.status AS endpointStatus,
    s.id AS sourceId,
    SUBSTRING_INDEX(s.code,'_', 1) AS sourceCode,
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
WHERE e.status = 'active'
"""


class ApiCatalogSourceError(RuntimeError):
    """Raised when the registry source cannot be loaded."""


class ApiCatalogRegistrySource:
    """从权威元数据源构建 `ApiCatalogEntry` 列表。

    功能：
        统一从业务 MySQL 直连抽取接口元数据，产出可直接入库到 Milvus 的标准化目录记录。

    Edge Cases:
        - SQL 里显式 `CAST(JSON AS CHAR)`，是为了消除不同 MySQL 驱动对 JSON 返回类型的差异
    """

    def __init__(self) -> None:
        self._pool: aiomysql.Pool | None = None

    async def load_entries(self) -> list[ApiCatalogEntry]:
        """仅从业务 MySQL 加载接口目录记录。

        Returns:
            标准化后的 `ApiCatalogEntry` 列表，且始终附带 builtin 字典接口。

        Raises:
            ApiCatalogSourceError: 当 MySQL 元数据不可用或返回空结果时抛出。
        """
        try:
            remote_entries = await self._load_mysql_entries()
        except Exception as exc:
            raise ApiCatalogSourceError(f"无法从 MySQL 加载注册表: {exc}") from exc
        return _append_builtin_entries(remote_entries)

    async def get_entry_by_id(self, api_id: str) -> ApiCatalogEntry | None:
        """按接口主键精确加载单条目录记录。

        功能：
            `direct` 快路不应该为了拿一条接口定义去重走 Milvus 或全量注册表加载。
            这里提供精确查找路径，让二跳场景直接对齐 `ui_api_endpoints.id`。

        Args:
            api_id: 目标接口 ID，对应业务元数据表主键。

        Returns:
            命中时返回单条 `ApiCatalogEntry`；未命中返回 `None`。

        Raises:
            ApiCatalogSourceError: 当 MySQL 查询失败时抛出。
        """
        builtin_entry = _find_builtin_entry_by_id(api_id)
        if builtin_entry is not None:
            return builtin_entry

        try:
            rows = await self._fetch_mysql_rows(_API_CATALOG_REGISTRY_SELECT_SQL, (api_id,))
        except Exception as exc:
            raise ApiCatalogSourceError(f"无法从 MySQL 加载接口 {api_id}: {exc}") from exc

        if not rows:
            return None
        return _build_entry_from_mysql_row(rows[0])

    async def _load_mysql_entries(self) -> list[ApiCatalogEntry]:
        """从业务 MySQL 直连抽取接口目录元数据。

        功能：
            直接对齐设计稿里的 `ui_api_endpoints + ui_api_sources + ui_api_tags` 三表拍平逻辑，
            避免在网关和 business-server 之间再绕一层 REST 元数据代理。
        """
        rows = await self._fetch_mysql_rows(_API_CATALOG_REGISTRY_SELECT_SQL)
        entries = [_build_entry_from_mysql_row(row) for row in rows]
        if not entries:
            raise ApiCatalogSourceError("MySQL metadata returned no endpoints")
        return _dedupe_by_signature(entries)

    async def _fetch_mysql_rows(
        self,
        sql: str,
        params: tuple[Any, ...] | None = None,
    ) -> list[dict[str, Any]]:
        """执行注册表元数据 SQL，并返回字典行结果。

        功能：
            全量加载和按主键精确查找共用同一套底层 SQL 访问入口，避免连接池和游标
            生命周期分叉后出现“一个路径能查、另一个路径忘了关连接”的隐性问题。
        """
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                if params is None:
                    await cursor.execute(sql)
                else:
                    await cursor.execute(sql, params)
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def _get_pool(self) -> aiomysql.Pool:
        """懒加载 API Catalog MySQL 连接池。"""
        if self._pool is None:
            logger.info(
                "Connecting to business MySQL host=%s port=%s db=%s timeout=%ss",
                settings.business_mysql_host,
                settings.business_mysql_port,
                settings.business_mysql_database,
                settings.api_catalog_mysql_connect_timeout_seconds,
            )
            self._pool = await aiomysql.create_pool(minsize=1, maxsize=5, **_build_business_mysql_conn_params())
        return self._pool

    async def close(self) -> None:
        """释放内部连接池。"""
        if self._pool is not None:
            self._pool.close()
            await self._pool.wait_closed()
            self._pool = None


def _build_business_mysql_conn_params() -> dict[str, str | int | float]:
    """从 `BUSINESS_MYSQL_*` 生成 API Catalog 直连配置。

    功能：
        API Catalog 的治理元数据本质属于业务库，不应再维持一套 `AI_MYSQL_*` 私有环境变量。
        这里统一改读业务库配置，同时让部署侧只维护一份 MySQL 连接来源。
    """
    return {
        "host": settings.business_mysql_host,
        "port": settings.business_mysql_port,
        "user": settings.business_mysql_user,
        "password": settings.business_mysql_password,
        "db": settings.business_mysql_database,
        "charset": "utf8mb4",
        "connect_timeout": settings.api_catalog_mysql_connect_timeout_seconds,
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
        "operationSafety": row.get("operationSafety"),
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
    operation_safety = _normalize_operation_safety(endpoint.get("operationSafety"))

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
        operation_safety=operation_safety,
        method=method,
        path=path,
        auth_required=auth_required,
        executor_config={
            # registry 条目统一切到 runtime invoke；只有 builtin / 特殊条目继续走旧直连执行器。
            "executor_type": "runtime_invoke",
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
            "operation_safety": operation_safety,
            "query_safe": operation_safety == "query",
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


def _append_builtin_entries(entries: list[ApiCatalogEntry]) -> list[ApiCatalogEntry]:
    by_signature = {(entry.method, entry.path): entry for entry in entries}
    dict_entry = _build_system_dict_entry()
    by_signature.setdefault((dict_entry.method, dict_entry.path), dict_entry)
    return list(by_signature.values())


def _find_builtin_entry_by_id(api_id: str) -> ApiCatalogEntry | None:
    """按 ID 匹配网关内置目录项。

    功能：
        内置字典接口不在业务 MySQL 中持久化；`direct` 快路如果命中这类接口，
        必须先在网关内置目录里完成一次短路匹配，避免多打一趟注定为空的 SQL。
    """
    dict_entry = _build_system_dict_entry()
    if dict_entry.id == api_id:
        return dict_entry
    return None


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
        operation_safety="query",
        method="GET",
        path="/api/system/dicts",
        auth_required=True,
        executor_config={
            "executor_type": "legacy_http",
            "source_id": "builtin",
            "source_code": "system",
            "source_name": "System Builtins",
            "auth_type": "bearer",
        },
        security_rules={
            "auth_required": True,
            "read_only": True,
            "operation_safety": "query",
            "query_safe": True,
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


def _dedupe_by_signature(entries: list[ApiCatalogEntry]) -> list[ApiCatalogEntry]:
    by_signature: dict[tuple[str, str], ApiCatalogEntry] = {}
    for entry in entries:
        by_signature[(entry.method, entry.path)] = entry
    return list(by_signature.values())


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


def _normalize_operation_safety(value: Any) -> str:
    """规范化接口安全语义。

    功能：
        `operation_safety` 是 /api-query 的硬安全边界。这里默认回退到 `mutation`，
        目的是在元数据缺失或脏值混入时宁可阻断，也不把未确认的接口放行到真实执行链路。
    """
    normalized = str(value or "mutation").strip().lower()
    if normalized == "query":
        return "query"
    elif normalized == "list":
        return "list"
    return "mutation"


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
