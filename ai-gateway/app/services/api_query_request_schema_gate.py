from __future__ import annotations

from collections.abc import Collection
from typing import Any

_RUNTIME_INVOKE_API_TEMPLATE = "/api/v1/ui-builder/runtime/endpoints/{id}/invoke"


def build_runtime_invoke_api(api_id: str | None) -> str:
    """把业务接口 ID 转成前端可直连的 runtime invoke 相对路径。"""

    normalized_api_id = str(api_id or "").strip()
    if not normalized_api_id:
        return ""
    return _RUNTIME_INVOKE_API_TEMPLATE.format(id=normalized_api_id)


def filter_request_schema_params(
    params: Any,
    *,
    allowed_fields: Collection[str] | None,
) -> dict[str, Any]:
    """按 request_schema 白名单过滤顶层请求参数。"""

    normalized_params = params if isinstance(params, dict) else {}
    if allowed_fields is None:
        return dict(normalized_params)
    normalized_allowed_fields = {
        str(field_name).strip()
        for field_name in (allowed_fields or [])
        if isinstance(field_name, str) and field_name.strip()
    }
    if not normalized_allowed_fields:
        return {}
    return {
        field_name: value
        for field_name, value in normalized_params.items()
        if isinstance(field_name, str) and field_name in normalized_allowed_fields
    }


def build_request_schema_gated_fields(
    api_id: str | None,
    *,
    param_source: str | None,
    params: Any,
    flow_num: str | None,
    created_by: str | None,
    allowed_fields: Collection[str] | None,
) -> dict[str, Any]:
    """统一产出带 request_schema gate 的 UI 请求元数据。"""

    normalized_params = filter_request_schema_params(params, allowed_fields=allowed_fields)
    is_body_request = (param_source or "").strip().lower() == "body"
    return {
        "api": build_runtime_invoke_api(api_id),
        "queryParams": {} if is_body_request else normalized_params,
        "body": normalized_params if is_body_request else {},
        "flowNum": flow_num or "",
        "createdBy": created_by or "",
    }
