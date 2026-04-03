"""
API Catalog — Business-Server 接口执行器

给定 ApiCatalogEntry + 提取的参数 + 用户 Token，
通过 httpx 调用 business-server，并将响应规范化为 List[Dict] 或 Dict。

设计约束：
- 透传用户 JWT Token（ai-gateway 不做二次鉴权）
- 按 response_data_path 自动展平嵌套 JSON
- 按 field_labels 映射字段名为中文
- 超时、4xx、5xx 各自处理，给出语义化错误

使用方式::

    from app.services.api_catalog.executor import ApiExecutor
    executor = ApiExecutor()
    data, total = await executor.call(entry, params, user_token="Bearer xxx")
"""
from __future__ import annotations

import logging
from functools import reduce
from typing import Any

import httpx

from app.core.config import settings
from app.models.schemas import ApiQueryExecutionResult, ApiQueryExecutionStatus
from app.services.api_catalog.schema import ApiCatalogEntry

logger = logging.getLogger(__name__)

class ApiExecutor:
    """通过 httpx 调用 business-server，规范化响应数据。"""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=settings.business_server_url,
                timeout=settings.business_server_timeout_seconds,
                follow_redirects=True,
            )
        return self._client

    async def call(
        self,
        entry: ApiCatalogEntry,
        params: dict[str, Any],
        user_token: str | None = None,
        trace_id: str | None = None,
    ) -> ApiQueryExecutionResult:
        """
        调用 business-server 接口，返回规范化数据。

        Args:
            entry: 接口目录记录
            params: LLM 提取到的参数
            user_token: 用户 JWT Token（格式 "Bearer xxx"），透传到 Authorization 头

        Returns:
            (data, total)
            - data: List[Dict]（列表数据）或 Dict（汇总数据）
            - total: 总记录数（分页时有值），否则为 len(data) 或 1
        """
        client = self._get_client()
        headers = {"Content-Type": "application/json"}
        if user_token and entry.auth_required:
            headers["Authorization"] = user_token

        try:
            if entry.method in ("GET", "DELETE"):
                response = await client.request(
                    method=entry.method,
                    url=entry.path,
                    params=params,
                    headers=headers,
                )
            else:
                response = await client.request(
                    method=entry.method,
                    url=entry.path,
                    json=params,
                    headers=headers,
                )
        except httpx.TimeoutException:
            timeout_seconds = settings.business_server_timeout_seconds
            return _error_result(f"接口调用超时（{timeout_seconds}s）: {entry.path}", trace_id=trace_id)
        except httpx.RequestError as exc:
            return _error_result(f"接口网络异常: {exc}", trace_id=trace_id)

        # 错误状态码处理
        if response.status_code == 401:
            return _error_result("用户未登录或 Token 已过期，请重新登录", trace_id=trace_id)
        if response.status_code == 403:
            return _error_result("无权限访问该接口，请联系管理员", trace_id=trace_id)
        if response.status_code == 404:
            return _error_result(f"接口不存在: {entry.path}", trace_id=trace_id)
        if response.status_code >= 400:
            body = _safe_json(response)
            msg = body.get("message") or body.get("msg") or response.text[:200]
            return _error_result(f"业务接口返回错误 {response.status_code}: {msg}", trace_id=trace_id)

        body = _safe_json(response)

        # 提取数据
        raw_data, total = _extract_data(body, entry.response_data_path)

        # 字段名中文映射
        normalized = _apply_field_labels(raw_data, entry.field_labels)
        if isinstance(normalized, list) and not normalized:
            return ApiQueryExecutionResult(
                status=ApiQueryExecutionStatus.EMPTY,
                data=[],
                total=total,
                trace_id=trace_id,
            )
        return ApiQueryExecutionResult(
            status=ApiQueryExecutionStatus.SUCCESS,
            data=normalized,
            total=total,
            trace_id=trace_id,
        )

    async def close(self) -> None:
        """关闭 httpx 客户端（生命周期结束时调用）。"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()


# ── 数据规范化工具 ───────────────────────────────────────────────────────────

def _safe_json(response: httpx.Response) -> dict[str, Any]:
    try:
        return response.json()
    except Exception:
        return {"raw": response.text}


def _extract_data(
    body: dict[str, Any],
    data_path: str,
) -> tuple[list[dict[str, Any]] | dict[str, Any], int]:
    """
    按 dot-notation 路径从响应体中提取数据。

    支持标准业务分页结构：
    {
        "code": 0,
        "data": {
            "list": [...],   ← response_data_path = "data.list"
            "total": 100
        }
    }
    """
    # 按 path 逐级取值
    keys = data_path.split(".") if data_path else []
    raw = body
    try:
        raw = reduce(lambda obj, key: obj[key], keys, raw)
    except (KeyError, TypeError):
        # path 不匹配，尝试常见回退路径
        for fallback in ("data", "result", "list", "records"):
            if fallback in body:
                raw = body[fallback]
                break

    # 尝试提取 total（适配 data.total 或 data/total）
    total = 0
    parent = body
    if len(keys) > 1:
        try:
            parent = reduce(lambda obj, key: obj[key], keys[:-1], body)
        except (KeyError, TypeError):
            pass
    total = (
        parent.get("total")
        or parent.get("totalCount")
        or parent.get("count")
        or body.get("total")
        or 0
    )

    if isinstance(raw, list):
        data = [row if isinstance(row, dict) else {"value": row} for row in raw]
        return data, int(total) if total else len(data)

    if isinstance(raw, dict):
        return raw, 1

    return [{"value": raw}], 1


def _apply_field_labels(
    data: list[dict[str, Any]] | dict[str, Any],
    field_labels: dict[str, str],
) -> list[dict[str, Any]] | dict[str, Any]:
    """将字段名按 field_labels 映射为中文（保留原字段名，新增中文 key）。"""
    if not field_labels:
        return data

    def rename_row(row: dict) -> dict:
        result = {}
        for k, v in row.items():
            label = field_labels.get(k)
            result[label if label else k] = v
        return result

    if isinstance(data, list):
        return [rename_row(row) for row in data]
    if isinstance(data, dict):
        return rename_row(data)
    return data


class ApiCallError(Exception):
    """业务接口调用失败异常。"""

    def __init__(self, message: str, status_code: int = 500) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.user_message = message


def _error_result(message: str, *, trace_id: str | None) -> ApiQueryExecutionResult:
    return ApiQueryExecutionResult(
        status=ApiQueryExecutionStatus.ERROR,
        data=None,
        total=0,
        error=message,
        trace_id=trace_id,
    )
