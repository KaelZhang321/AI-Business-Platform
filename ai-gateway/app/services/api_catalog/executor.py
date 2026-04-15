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
from collections.abc import Collection
from typing import Any

import httpx

from app.core.config import settings
from app.models.schemas import ApiQueryExecutionResult, ApiQueryExecutionStatus
from app.services.api_catalog.schema import ApiCatalogEntry

logger = logging.getLogger(__name__)
_DEFAULT_ALLOWED_EXECUTOR_METHODS = frozenset({"GET"})
_QUERY_ALLOWED_EXECUTOR_METHODS = frozenset({"GET", "POST"})
_LEGACY_BUILTIN_API_IDS = frozenset({"system_dicts_v1"})
_LEGACY_BUILTIN_SOURCE_IDS = frozenset({"builtin"})


class LegacyApiExecutor:
    """旧版直连执行器。

    功能：
        保留当前“直接调用 business-server 路径”的历史行为，专门服务 builtin / 特殊条目，
        并作为 runtime invoke 的快速回滚路径，保证灰度阶段可以一键切回老链路。
    """

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        """懒加载旧版 business-server HTTP 客户端。"""
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
        allow_methods: Collection[str] | None = None,
        user_id: str | None = None,
    ) -> ApiQueryExecutionResult:
        """按历史模式调用 business-server 并规范化响应。"""
        allowed_methods = _normalize_allowed_methods(allow_methods)
        if entry.method not in allowed_methods:
            return _build_method_blocked_result(entry, allowed_methods, trace_id=trace_id)

        client = self._get_client()
        headers = _build_gateway_headers(entry, user_token)

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
            return _build_timeout_result(
                timeout_seconds=settings.business_server_timeout_seconds,
                path=entry.path,
                trace_id=trace_id,
            )
        except httpx.RequestError as exc:
            return _build_request_error_result(entry, exc, trace_id=trace_id)

        http_error_result = _build_http_error_result(response, entry, trace_id=trace_id)
        if http_error_result is not None:
            return http_error_result
        return _finalize_success_result(_safe_json(response), entry, trace_id=trace_id)

    async def close(self) -> None:
        """关闭底层 httpx 客户端。"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()


class RuntimeInvokeExecutor:
    """runtime invoke 执行器。

    功能：
        把 `ui_api_endpoints` 的查询接口统一转成 business-server 的 runtime invoke 请求壳，
        这样 ai-gateway 不再关心底层系统的真实地址和鉴权细节，而是复用 business-server
        已有的运行时编排与审计日志能力。

    返回值约束：
        - 只允许 `operation_safety=query && method in {GET, POST}` 的条目进入真实发送
        - business-server 的统一包壳会先拆 `data`，再复用既有 `response_data_path`
        - `useSampleWhenEmpty` 固定为 `false`，避免生成链路把样例数据误当真实数据
    """

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        """懒加载 runtime invoke 客户端。"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=settings.api_query_runtime_timeout_seconds,
                follow_redirects=True,
            )
        return self._client

    async def call(
        self,
        entry: ApiCatalogEntry,
        params: dict[str, Any],
        user_token: str | None = None,
        trace_id: str | None = None,
        allow_methods: Collection[str] | None = None,
        user_id: str | None = None,
    ) -> ApiQueryExecutionResult:
        """通过 runtime invoke 调用查询接口。

        功能：
            当目录项被切到 runtime invoke 模式后，这里负责把“查询参数、认证凭证、请求级身份、
            追踪 ID”压平成 business-server 期望的统一请求壳。把身份映射集中在执行器层，
            是为了让 workflow 只表达业务计划，而不感知不同执行后端的协议差异。

        Args:
            entry: 当前命中的目录接口定义。
            params: 已完成参数绑定的业务入参。
            user_token: 需要透传给下游的用户认证头。
            trace_id: 当前 `/api-query` 请求链路的唯一追踪键。
            allow_methods: 执行器级方法白名单，默认只允许 GET / POST 查询。
            user_id: 当前请求最终认定的用户主键，会写入 runtime invoke 的 `createdBy`。

        Returns:
            标准化后的 `ApiQueryExecutionResult`，屏蔽 runtime invoke 的协议细节。

        Edge Cases:
            - mutation 接口会在真正发请求前被硬阻断，避免网关误放行写操作
            - 非 HTTP 上下文缺少 `trace_id` / `user_id` 时，会在 payload 构造阶段自动回退配置
        """
        if entry.operation_safety == "mutation":
            logger.warning(
                "stage4 runtime invoke blocked unsafe entry trace_id=%s api_id=%s safety=%s",
                trace_id or "-",
                entry.id,
                entry.operation_safety,
            )
            return _error_result(
                f"执行器已拦截非查询语义接口: {entry.id}",
                trace_id=trace_id,
                error_code="EXECUTOR_UNSAFE_OPERATION",
            )

        allowed_methods = _normalize_allowed_methods(allow_methods or _QUERY_ALLOWED_EXECUTOR_METHODS)
        if entry.method not in allowed_methods:
            return _build_method_blocked_result(entry, allowed_methods, trace_id=trace_id)

        url = _build_runtime_invoke_url(entry)
        payload = _build_runtime_invoke_payload(entry, params, trace_id=trace_id, user_id=user_id)
        client = self._get_client()
        headers = _build_gateway_headers(entry, user_token, always_forward_auth=True, user_id=user_id)

        try:
            response = await client.post(url, json=payload, headers=headers)
        except httpx.TimeoutException:
            return _build_timeout_result(
                timeout_seconds=settings.api_query_runtime_timeout_seconds,
                path=url,
                trace_id=trace_id,
            )
        except httpx.RequestError as exc:
            return _error_result(
                f"runtime invoke 网络异常: {exc}",
                trace_id=trace_id,
                error_code="RUNTIME_INVOKE_REQUEST_ERROR",
                retryable=True,
            )

        response = await self._fallback_retry_without_user_id_header(
            client=client,
            url=url,
            payload=payload,
            headers=headers,
            primary_response=response,
            trace_id=trace_id,
            api_id=entry.id,
        )

        if response.status_code == 401:
            return _error_result(
                "用户未登录或 Token 已过期，请重新登录",
                trace_id=trace_id,
                error_code="UPSTREAM_UNAUTHORIZED",
            )
        if response.status_code == 403:
            return _error_result(
                "无权限访问该接口，请联系管理员",
                trace_id=trace_id,
                error_code="UPSTREAM_FORBIDDEN",
            )
        if response.status_code >= 400:
            body = _safe_json(response)
            msg = body.get("message") or body.get("msg") or response.text[:200]
            return _error_result(
                f"runtime invoke 返回错误 {response.status_code}: {msg}",
                trace_id=trace_id,
                error_code="RUNTIME_INVOKE_HTTP_ERROR",
                retryable=response.status_code >= 500,
            )

        payload_body = _safe_json(response)
        if int(payload_body.get("code") or 500) != 200:
            return _error_result(
                f"runtime invoke 业务失败: {payload_body.get('message') or payload_body.get('msg') or 'unknown'}",
                trace_id=trace_id,
                error_code="RUNTIME_INVOKE_BUSINESS_ERROR",
            )

        raw_body = payload_body.get("data")
        if not isinstance(raw_body, dict):
            if raw_body in (None, "", [], {}):
                return ApiQueryExecutionResult(
                    status=ApiQueryExecutionStatus.EMPTY,
                    data=[],
                    total=0,
                    trace_id=trace_id,
                )
            raw_body = {"data": raw_body}
        return _finalize_success_result(raw_body, entry, trace_id=trace_id)

    async def close(self) -> None:
        """关闭底层 httpx 客户端。"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def _fallback_retry_without_user_id_header(
        self,
        *,
        client: httpx.AsyncClient,
        url: str,
        payload: dict[str, Any],
        headers: dict[str, str],
        primary_response: httpx.Response,
        trace_id: str | None,
        api_id: str,
    ) -> httpx.Response:
        """在 runtime invoke 5xx 且携带 `X-User-Id` 时执行一次兼容重试。

        功能：
            `X-User-Id` 是网关给 runtime invoke 的主身份线索，但在本地直连调试或上游
            身份头被错误注入时，下游可能因为该值无法映射而返回 5xx。为了避免把“身份头脏值”
            直接放大成查询全链路失败，这里仅在 5xx 下做一次无损降级重试：
            保留 Authorization，不携带 `X-User-Id` 再请求一次。

        Args:
            client: runtime invoke 的 HTTP 客户端。
            url: 下游 runtime invoke 地址。
            payload: 本次调用请求体。
            headers: 首次调用请求头。
            primary_response: 首次调用响应。
            trace_id: 当前链路追踪 ID。
            api_id: 当前目录接口 ID，用于日志定位。

        Returns:
            默认返回首次响应；若降级重试成功且状态码进入非 5xx，则返回重试响应。

        Edge Cases:
            - 只在“首调是 5xx 且存在 X-User-Id”时触发，避免污染正常链路时延
            - 重试阶段网络异常不会覆盖首调结果，保证错误语义稳定可回放
        """
        if primary_response.status_code < 500:
            return primary_response
        if "X-User-Id" not in headers:
            return primary_response

        fallback_headers = dict(headers)
        fallback_headers.pop("X-User-Id", None)
        logger.warning(
            "stage4 runtime invoke fallback retry without X-User-Id trace_id=%s api_id=%s primary_status=%s",
            trace_id or "-",
            api_id,
            primary_response.status_code,
        )
        try:
            fallback_response = await client.post(url, json=payload, headers=fallback_headers)
        except httpx.RequestError as exc:
            logger.warning(
                "stage4 runtime invoke fallback retry failed trace_id=%s api_id=%s reason=%s",
                trace_id or "-",
                api_id,
                exc,
            )
            return primary_response
        if fallback_response.status_code < 500:
            return fallback_response
        return primary_response


class ApiExecutor:
    """执行器路由层。

    功能：
        根据目录项的 `executor_config.executor_type` 和开关配置，在旧直连执行器与
        runtime invoke 执行器之间做最终分发，让 DAG 执行总线不感知底层执行模式。
    """

    def __init__(
        self,
        *,
        legacy_executor: LegacyApiExecutor | None = None,
        runtime_executor: RuntimeInvokeExecutor | None = None,
    ) -> None:
        self._legacy_executor = legacy_executor or LegacyApiExecutor()
        self._runtime_executor = runtime_executor or RuntimeInvokeExecutor()

    async def call(
        self,
        entry: ApiCatalogEntry,
        params: dict[str, Any],
        user_token: str | None = None,
        trace_id: str | None = None,
        allow_methods: Collection[str] | None = None,
        user_id: str | None = None,
    ) -> ApiQueryExecutionResult:
        """路由到实际执行器并透传统一调用契约。

        功能：
            `user_id` 对 legacy 直连路径没有意义，但 runtime invoke 需要把“本次查询最终归属
            于谁”写入请求壳。统一把该字段挂在门面层，是为了让 workflow / LangGraph 只维护
            一份执行接口，而不用感知底层执行模式差异。
        """
        executor, executor_type = self._resolve_executor(entry)
        effective_allow_methods = allow_methods or _derive_default_allow_methods(entry, executor_type)
        return await executor.call(
            entry,
            params,
            user_token=user_token,
            trace_id=trace_id,
            allow_methods=effective_allow_methods,
            user_id=user_id,
        )

    async def close(self) -> None:
        """关闭所有底层执行器客户端。"""
        await self._legacy_executor.close()
        await self._runtime_executor.close()

    def _resolve_executor(self, entry: ApiCatalogEntry) -> tuple[LegacyApiExecutor | RuntimeInvokeExecutor, str]:
        """根据目录项类型与开关决定最终执行器。

        功能：
            这里故意把路由条件收敛成很少的几个维度，避免“业务安全语义”和“执行物理路径”
            混在一起。安全是否允许由 route/planner/runtime executor 多层兜底，物理分发只看：

            1. 目录项是否显式声明 `runtime_invoke`
            2. 全局 runtime 开关是否开启
        """
        executor_type = str(entry.executor_config.get("executor_type") or "").strip().lower()
        if executor_type == "runtime_invoke" and settings.api_query_runtime_enabled:
            return self._runtime_executor, executor_type
        if executor_type == "legacy_http":
            return self._legacy_executor, executor_type
        if _should_default_to_runtime_invoke(entry):
            if settings.api_query_runtime_enabled:
                logger.warning(
                    "stage4 inferred runtime executor for stale catalog entry id=%s path=%s",
                    entry.id,
                    entry.path,
                )
                return self._runtime_executor, "runtime_invoke"
            return self._legacy_executor, "legacy_http"
        return self._legacy_executor, executor_type


# ── 数据规范化工具 ───────────────────────────────────────────────────────────


def _build_gateway_headers(
    entry: ApiCatalogEntry,
    user_token: str | None,
    *,
    always_forward_auth: bool = False,
    user_id: str | None = None,
) -> dict[str, str]:
    """构造网关透传请求头。

    功能：
        ai-gateway 只做查询编排，不自行改写业务身份。这里统一在两个执行器里复用同一套
        头部拼装规则，确保 runtime invoke 和旧直连路径都遵守相同的鉴权边界。

        当调用 runtime invoke 时，下游需要拿 `X-User-Id` 做审计与数据权限判定，因此把
        已经在网关完成可信判定的 user_id 原样透传，避免下游再做一次身份推断。
    """
    headers = {"Content-Type": "application/json"}
    if user_token and (always_forward_auth or entry.auth_required):
        headers["Authorization"] = user_token
    normalized_user_id = user_id.strip() if user_id else ""
    if normalized_user_id:
        headers["X-User-Id"] = normalized_user_id
    return headers


def _should_default_to_runtime_invoke(entry: ApiCatalogEntry) -> bool:
    """为旧索引目录项推断 runtime invoke 执行器。

    功能：
        这次切换把 MySQL 注册表条目统一收口到 runtime invoke，但线上可能仍保留旧 Milvus
        索引，里面的 `executor_config` 还没有 `executor_type`。如果不在这里做兼容推断，
        `/api-query` 会继续走旧直连路径，表现成“代码已发布但流量没有真正切换”。

    Returns:
        `True` 表示这是一个历史注册表条目，应默认走 runtime invoke；`False` 表示保留 legacy。
    """
    if entry.id in _LEGACY_BUILTIN_API_IDS:
        return False

    source_id = str(entry.executor_config.get("source_id") or "").strip().lower()
    if source_id in _LEGACY_BUILTIN_SOURCE_IDS:
        return False

    # 旧版 Milvus 索引里的注册表条目通常没有 executor_type，但仍会保留来源系统元数据。
    # 只要命中这些“来自 ui_api_endpoints/ui_api_sources”的痕迹，就默认切到 runtime invoke。
    return any(
        entry.executor_config.get(field_name)
        for field_name in ("source_id", "source_code", "source_name", "base_url", "auth_type")
    )


def _build_method_blocked_result(
    entry: ApiCatalogEntry,
    allowed_methods: Collection[str],
    *,
    trace_id: str | None,
) -> ApiQueryExecutionResult:
    """构造“执行器白名单拦截”结果。"""
    logger.warning(
        "stage4 executor blocked method trace_id=%s method=%s path=%s allowed_methods=%s",
        trace_id or "-",
        entry.method,
        entry.path,
        sorted(allowed_methods),
    )
    return _error_result(
        f"执行器已拦截非白名单接口调用: {entry.method} {entry.path}",
        trace_id=trace_id,
        error_code="EXECUTOR_METHOD_NOT_ALLOWED",
    )


def _build_timeout_result(
    *,
    timeout_seconds: float,
    path: str,
    trace_id: str | None,
) -> ApiQueryExecutionResult:
    """统一构造超时错误结果。"""
    logger.warning(
        "stage4 upstream timeout trace_id=%s path=%s timeout_seconds=%s",
        trace_id or "-",
        path,
        timeout_seconds,
    )
    return _error_result(
        f"接口调用超时（{timeout_seconds}s）: {path}",
        trace_id=trace_id,
        error_code="UPSTREAM_TIMEOUT",
        retryable=True,
    )


def _build_request_error_result(
    entry: ApiCatalogEntry,
    exc: httpx.RequestError,
    *,
    trace_id: str | None,
) -> ApiQueryExecutionResult:
    """统一构造底层网络错误结果。"""
    logger.warning(
        "stage4 upstream request error trace_id=%s method=%s path=%s error=%s",
        trace_id or "-",
        entry.method,
        entry.path,
        exc,
    )
    return _error_result(
        f"接口网络异常: {exc}",
        trace_id=trace_id,
        error_code="UPSTREAM_REQUEST_ERROR",
        retryable=True,
    )


def _build_http_error_result(
    response: httpx.Response,
    entry: ApiCatalogEntry,
    *,
    trace_id: str | None,
) -> ApiQueryExecutionResult | None:
    """把 HTTP 层错误折叠成统一执行结果。

    功能：
        route 层应该消费业务语义化错误，而不是四处判断 401/403/404。这里集中吸收
        上游 HTTP 差异，保证 legacy 与 runtime fallback 链路的错误口径一致。
    """
    if response.status_code == 401:
        return _error_result(
            "用户未登录或 Token 已过期，请重新登录",
            trace_id=trace_id,
            error_code="UPSTREAM_UNAUTHORIZED",
        )
    if response.status_code == 403:
        return _error_result(
            "无权限访问该接口，请联系管理员",
            trace_id=trace_id,
            error_code="UPSTREAM_FORBIDDEN",
        )
    if response.status_code == 404:
        return _error_result(
            f"接口不存在: {entry.path}",
            trace_id=trace_id,
            error_code="UPSTREAM_NOT_FOUND",
        )
    if response.status_code < 400:
        return None

    body = _safe_json(response)
    msg = body.get("message") or body.get("msg") or response.text[:200]
    logger.warning(
        "stage4 upstream rejected trace_id=%s method=%s path=%s status=%s message=%s",
        trace_id or "-",
        entry.method,
        entry.path,
        response.status_code,
        msg,
    )
    return _error_result(
        f"业务接口返回错误 {response.status_code}: {msg}",
        trace_id=trace_id,
        error_code="UPSTREAM_HTTP_ERROR",
        retryable=response.status_code >= 500,
    )


def _finalize_success_result(
    body: dict[str, Any],
    entry: ApiCatalogEntry,
    *,
    trace_id: str | None,
) -> ApiQueryExecutionResult:
    """把成功响应统一折叠为 `ApiQueryExecutionResult`。

    功能：
        runtime invoke 与旧直连路径最终都必须落回同一套 `response_data_path + field_labels`
        处理逻辑，否则前端看到的 UI 行为会随着执行器不同而漂移。
    """
    raw_data, total = _extract_data(body, entry.response_data_path)
    normalized = _apply_field_labels(raw_data, entry.field_labels)
    if isinstance(normalized, dict) and not normalized:
        return ApiQueryExecutionResult(
            status=ApiQueryExecutionStatus.EMPTY,
            data=[],
            total=0,
            trace_id=trace_id,
        )
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


def _derive_default_allow_methods(entry: ApiCatalogEntry, executor_type: str) -> set[str]:
    """根据目录项语义推导默认方法白名单。

    功能：
        执行器路由层需要既支持“builtin 永远走 GET 旧路径”，也支持“runtime 关闭时，
        query POST 可以临时回退到旧执行器”。因此默认白名单不能再是一个全局常量，
        而要结合目录项语义做最小放行。
    """
    if executor_type == "runtime_invoke":
        return {entry.method} if entry.method in _QUERY_ALLOWED_EXECUTOR_METHODS else set(_DEFAULT_ALLOWED_EXECUTOR_METHODS)
    if entry.operation_safety == "query" and entry.method in _QUERY_ALLOWED_EXECUTOR_METHODS:
        return {entry.method}
    return set(_DEFAULT_ALLOWED_EXECUTOR_METHODS)


def _build_runtime_invoke_url(entry: ApiCatalogEntry) -> str:
    """拼装 runtime invoke URL。

    功能：
        运行时入口必须做成可配置，便于灰度、回滚和多环境切换；这里只保留 `{id}`
        一个模板变量，避免 URL 拼装散落在执行流程里。
    """
    try:
        return settings.api_query_runtime_invoke_url_template.format(id=entry.id)
    except KeyError as exc:
        raise RuntimeError("API_QUERY_RUNTIME_INVOKE_URL_TEMPLATE 缺少 {id} 占位符") from exc


def _resolve_runtime_flow_num(trace_id: str | None) -> str:
    """为 runtime invoke 决定最终 `flowNum`。

    功能：
        `flowNum` 现在承担的是跨 `ai-gateway` 与 `business-server runtime invoke` 的统一追踪键，
        因此主路径必须直接复用当前请求 `trace_id`。同时保留配置回退，是为了兼容 CLI、单测
        或运维脚本可能直接调用执行器而没有 HTTP Trace 上下文的场景。

    Args:
        trace_id: 当前请求链路 Trace ID。

    Returns:
        优先返回当前请求 `trace_id`；缺失时回退到历史配置值。

    Edge Cases:
        - 空白 `trace_id` 会被视为缺失，避免把无效追踪键写入下游日志
    """
    normalized_trace_id = trace_id.strip() if trace_id else ""
    if normalized_trace_id:
        return normalized_trace_id
    return str(settings.api_query_runtime_flow_num)


def _resolve_runtime_created_by(user_id: str | None) -> str:
    """为 runtime invoke 决定最终 `createdBy`。

    功能：
        查询链路的 `createdBy` 不再是部署配置，而是本次请求最终认定的用户主键。只有在
        非 HTTP 场景没有请求级 `user_id` 时，才回退到旧配置，保证历史脚本不因为新增
        请求级身份依赖而直接失效。

    Args:
        user_id: 当前请求最终认定的用户主键。

    Returns:
        优先返回请求级 `user_id`；缺失时回退到历史配置值。

    Edge Cases:
        - 仅包含空白字符的 `user_id` 会被视为缺失，避免污染审计字段
    """
    normalized_user_id = user_id.strip() if user_id else ""
    if normalized_user_id:
        return normalized_user_id
    return settings.api_query_runtime_created_by


def _build_runtime_invoke_payload(
    entry: ApiCatalogEntry,
    params: dict[str, Any],
    *,
    trace_id: str | None,
    user_id: str | None,
) -> dict[str, Any]:
    """构造 runtime invoke 请求壳。

    功能：
        GET 查询接口把业务参数落到 `queryParams`，POST 查询接口落到 `body`，同时把
        请求级 `trace_id` / `user_id` 映射成 `flowNum` / `createdBy`。这样下游 runtime invoke
        日志就能直接串回当前 `/api-query` 链路，而不需要再维护一套独立流水号。

    Args:
        entry: 当前命中的目录接口实体。
        params: 已完成参数提取与绑定的业务参数。
        trace_id: 当前请求 Trace ID，用作 runtime invoke 的统一追踪键。
        user_id: 当前请求最终认定的用户主键，用作 runtime invoke 的调用人标识。

    Returns:
        符合 `ui-builder/runtime/endpoints/{id}/invoke` 契约的请求体。

    Edge Cases:
        - 非 HTTP 触发场景缺少 `trace_id` / `user_id` 时，会回退到历史配置，避免运维脚本断裂
    """
    runtime_query_params: dict[str, Any] = {}
    business_params = dict(params)

    if entry.method == "GET":
        runtime_query_params.update(business_params)
        runtime_body: dict[str, Any] = {}
    else:
        runtime_body = business_params

    return {
        "flowNum": _resolve_runtime_flow_num(trace_id),
        "queryParams": runtime_query_params,
        "createdBy": _resolve_runtime_created_by(user_id),
        # "useSampleWhenEmpty": False,
        "body": runtime_body,
    }


def _safe_json(response: httpx.Response) -> dict[str, Any]:
    """安全解析上游 JSON，失败时回落为原始文本。"""
    try:
        return response.json()
    except Exception:
        return {"raw": response.text}


def _normalize_allowed_methods(allow_methods: Collection[str] | None) -> set[str]:
    """规范化执行器方法白名单。

    功能：
        执行器本身不应该依赖调用方永远传对大小写或完整白名单；这里统一做一次
        标准化，确保“默认只读”是稳定生效的安全底线。

    Args:
        allow_methods: 调用方声明允许执行的 HTTP 方法集合。

    Returns:
        全部转成大写后的方法集合；若传入为空，则回退到默认 `{"GET"}`。

    Edge Cases:
        - 空字符串会被静默丢弃，避免把脏值误判成合法方法
        - 若调用方误传单个字符串 `"GET"`，会被当成单元素白名单而不是拆成字符集合
        - 归一化后若结果为空，仍回退到默认只读集合
    """
    raw_methods: Collection[str]
    if isinstance(allow_methods, str):
        raw_methods = [allow_methods]
    else:
        raw_methods = allow_methods or _DEFAULT_ALLOWED_EXECUTOR_METHODS

    normalized_methods = {
        method.strip().upper()
        for method in raw_methods
        if method and method.strip()
    }
    return normalized_methods or set(_DEFAULT_ALLOWED_EXECUTOR_METHODS)


def _extract_data(
    body: dict[str, Any],
    data_path: str,
) -> tuple[list[dict[str, Any]] | dict[str, Any], int]:
    """
    按 dot-notation 路径从响应体中提取数据。

    功能：
        将不同后端返回的分页/非分页结构折叠为统一的 `data + total` 语义。

    Args:
        body: 上游接口返回的 JSON 响应体。
        data_path: 注册表中声明的数据路径，例如 `data.list`。

    Returns:
        一个 `(data, total)` 二元组，其中 `data` 只会是列表或字典。

    Edge Cases:
        - `data_path` 不匹配时，会尝试 `data/result/list/records` 等常见兜底路径
        - `null`、空字符串等无业务意义的值会直接降级为空结果
    """
    keys = [segment for segment in (data_path or "").split(".") if segment]
    raw = _resolve_path_value(body, keys)
    parent = _resolve_path_value(body, keys[:-1]) if len(keys) > 1 else body

    if raw is None and keys:
        # 目录里的 response_data_path 来自自动清洗，老数据存在口径偏差。
        # 这里先做稳定回退，避免单个接口数据层级变动把整条查询链路打成空。
        for fallback in ("data", "result", "payload", "list", "records"):
            if fallback in body:
                raw = body[fallback]
                parent = body
                break

    # 业务系统常见分页结构是 `data -> records/list`，详情结构可能藏在 `records.summaryCardDTO`。
    # 为了减少每个接口都手工改 response_data_path，这里做一次有限深度的语义拆箱。
    normalized_raw, total_anchor = _unwrap_common_result_shape(raw)
    total = _resolve_total_from_candidates(total_anchor, parent, body)

    if isinstance(normalized_raw, list):
        data = [row if isinstance(row, dict) else {"value": row} for row in normalized_raw]
        return data, int(total) if total else len(data)

    if isinstance(normalized_raw, dict):
        return normalized_raw, 1

    if normalized_raw in (None, "", []):
        return [], 0

    return [{"value": normalized_raw}], 1


def _resolve_path_value(payload: Any, path_segments: list[str]) -> Any | None:
    """按 dot-path 读取节点，读取失败返回 `None`。"""
    current = payload
    try:
        for segment in path_segments:
            if not isinstance(current, dict):
                return None
            current = current[segment]
        return current
    except KeyError:
        return None


def _unwrap_common_result_shape(raw: Any) -> tuple[Any, dict[str, Any] | None]:
    """按常见业务返回结构拆箱，返回 `(normalized_raw, total_anchor)`。

    功能：
        `api-query` 对接多个业务系统后，列表数据经常被包在 `records/list/rows/items`，
        详情摘要又常放在 `records.summaryCardDTO`。这里统一做有限规则拆箱，让 catalog 的
        `response_data_path` 不用为每个系统写一套特例路径。

    Returns:
        - `normalized_raw`: 实际用于渲染的数据主体（列表/对象/标量）
        - `total_anchor`: 若命中分页容器，返回该容器用于提取 total；否则返回 `None`
    """
    if not isinstance(raw, dict):
        return raw, None

    collection_keys = ("records", "list", "rows", "items")
    for key in collection_keys:
        value = raw.get(key)
        if isinstance(value, list):
            return value, raw

    # 某些系统会多包一层 `records` 或 `payload`，这里再下探一层找列表容器。
    for wrapper_key in ("records", "payload", "result", "data"):
        wrapper = raw.get(wrapper_key)
        if not isinstance(wrapper, dict):
            continue
        for key in collection_keys:
            value = wrapper.get(key)
            if isinstance(value, list):
                return value, wrapper

    # 详情接口常见结构：data.records.summaryCardDTO
    records_block = raw.get("records")
    if isinstance(records_block, dict):
        summary_card = records_block.get("summaryCardDTO")
        if isinstance(summary_card, dict):
            return summary_card, records_block

    summary_card = raw.get("summaryCardDTO")
    if isinstance(summary_card, dict):
        return summary_card, raw

    return raw, None


def _resolve_total_from_candidates(*candidates: Any) -> int:
    """从多个候选容器中提取分页总数。"""
    total_keys = ("total", "totalCount", "count", "recordsTotal", "rowTotal")
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        for key in total_keys:
            value = candidate.get(key)
            try:
                if value is not None:
                    normalized = int(value)
                    if normalized >= 0:
                        return normalized
            except (TypeError, ValueError):
                continue
    return 0


def _apply_field_labels(
    data: list[dict[str, Any]] | dict[str, Any],
    field_labels: dict[str, str],
) -> list[dict[str, Any]] | dict[str, Any]:
    """将字段名按 field_labels 映射为中文。

    功能：
        在网关层收敛多系统字段口径，让后续 UI 层更偏向“展示问题”而不是“字段翻译问题”。
    """
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
    """业务接口调用失败异常。

    当前阶段保留该异常类型，便于后续需要切换为异常驱动风格时复用统一语义。
    """

    def __init__(self, message: str, status_code: int = 500) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.user_message = message


def _error_result(
    message: str,
    *,
    trace_id: str | None,
    error_code: str | None = None,
    retryable: bool = False,
) -> ApiQueryExecutionResult:
    """构造统一错误结果，避免 route 层再感知 HTTP 客户端细节。"""
    return ApiQueryExecutionResult(
        status=ApiQueryExecutionStatus.ERROR,
        data=None,
        total=0,
        error=message,
        error_code=error_code,
        retryable=retryable,
        trace_id=trace_id,
    )
