from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

import httpx
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


class ApiCatalogSourceError(RuntimeError):
    """Raised when the registry source cannot be loaded."""


class ApiCatalogRegistrySource:
    """Build `ApiCatalogEntry` records from the authoritative registry source."""

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client

    async def load_entries(self, config_path: str | None = None) -> list[ApiCatalogEntry]:
        source_mode = settings.api_catalog_source_mode.strip().lower()
        if source_mode not in {"yaml", "ui_builder", "hybrid"}:
            raise ApiCatalogSourceError(f"Unsupported api catalog source mode: {source_mode}")
        overlay_entries = _load_overlay_entries(config_path)

        if source_mode == "yaml":
            return _append_builtin_entries(overlay_entries)

        remote_entries: list[ApiCatalogEntry] = []
        try:
            remote_entries = await self._load_ui_builder_entries()
        except Exception as exc:
            if source_mode == "ui_builder":
                raise ApiCatalogSourceError(f"无法从 UI Builder 加载注册表: {exc}") from exc
            logger.warning("Falling back to YAML api catalog source: %s", exc)

        if not remote_entries:
            return _append_builtin_entries(overlay_entries)

        return _append_builtin_entries(_merge_overlay_entries(remote_entries, overlay_entries))

    async def _load_ui_builder_entries(self) -> list[ApiCatalogEntry]:
        sources = await self._fetch_paged("/api/v1/ui-builder/sources")

        entries: list[ApiCatalogEntry] = []
        for source in sources:
            source_id = source.get("id")
            if not source_id:
                continue
            endpoints = await self._fetch_paged(f"/api/v1/ui-builder/sources/{source_id}/endpoints")
            for endpoint in endpoints:
                entries.append(_build_entry(source, endpoint))

        if not entries:
            raise ApiCatalogSourceError("UI Builder metadata returned no endpoints")
        return _dedupe_by_signature(entries)

    async def _fetch_paged(self, path: str) -> list[dict[str, Any]]:
        page = 1
        size = settings.ui_builder_metadata_page_size
        items: list[dict[str, Any]] = []

        while True:
            response = await self._get_client().get(path, params={"page": page, "size": size})
            if response.status_code >= 400:
                raise ApiCatalogSourceError(f"HTTP {response.status_code} from {path}")

            payload = response.json()
            if payload.get("code") != 200:
                raise ApiCatalogSourceError(f"Unexpected response code from {path}: {payload.get('code')}")

            page_data = payload.get("data") or {}
            page_items = page_data.get("data") or []
            items.extend(item for item in page_items if isinstance(item, dict))

            total = int(page_data.get("total") or 0)
            if not page_items or not total or len(items) >= total:
                break
            page += 1

        return items

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            headers = {}
            if settings.ui_builder_metadata_token:
                token = settings.ui_builder_metadata_token
                headers["Authorization"] = token if token.startswith("Bearer ") else f"Bearer {token}"
            self._client = httpx.AsyncClient(
                base_url=settings.business_server_url.rstrip("/"),
                timeout=settings.ui_builder_metadata_timeout_seconds,
                headers=headers,
                follow_redirects=True,
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()


def _build_entry(source: dict[str, Any], endpoint: dict[str, Any]) -> ApiCatalogEntry:
    method = str(endpoint.get("method") or "GET").upper()
    path = str(endpoint.get("path") or "")
    name = str(endpoint.get("name") or "").strip()
    summary = str(endpoint.get("summary") or "").strip()

    request_schema = _safe_json_loads(endpoint.get("requestSchema"))
    response_schema = _safe_json_loads(endpoint.get("responseSchema"))
    sample_response = _safe_json_loads(endpoint.get("sampleResponse"))

    auth_type = str(source.get("authType") or "").strip()
    auth_required = auth_type.lower() not in {"", "none", "public", "anonymous"}
    source_code = str(source.get("code") or "").strip()
    source_name = str(source.get("name") or "").strip()
    tag_name = _first_non_empty(endpoint.get("tagName"), endpoint.get("tagId"))

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
    merged = overlay_entry.model_copy(deep=True)
    merged.domain = remote_entry.domain or overlay_entry.domain
    merged.env = remote_entry.env or overlay_entry.env
    merged.status = remote_entry.status or overlay_entry.status
    merged.tag_name = remote_entry.tag_name or overlay_entry.tag_name
    merged.auth_required = remote_entry.auth_required
    merged.executor_config = {**remote_entry.executor_config, **overlay_entry.executor_config}
    merged.security_rules = {**remote_entry.security_rules, **overlay_entry.security_rules}
    if not merged.description:
        merged.description = remote_entry.description
    if not merged.example_queries:
        merged.example_queries = remote_entry.example_queries
    if not merged.tags:
        merged.tags = remote_entry.tags
    if not merged.business_intents:
        merged.business_intents = remote_entry.business_intents
    if not merged.field_labels:
        merged.field_labels = remote_entry.field_labels
    return merged


def _append_builtin_entries(entries: list[ApiCatalogEntry]) -> list[ApiCatalogEntry]:
    by_signature = {(entry.method, entry.path): entry for entry in entries}
    dict_entry = _build_system_dict_entry()
    by_signature.setdefault((dict_entry.method, dict_entry.path), dict_entry)
    return list(by_signature.values())


def _build_system_dict_entry() -> ApiCatalogEntry:
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


def _normalize_domain(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")
    return normalized or "generic"


def _normalize_tag_name(value: str | None) -> str | None:
    if not value:
        return None
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")
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
