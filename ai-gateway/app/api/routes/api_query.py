"""
API Query 路由

用户自然语言 → API Catalog 语义检索 → LLM 参数提取 → business-server 调用
→ 响应规范化 → DynamicUIService → json-render UI Spec

端点：
    POST /api/v1/api-query       非流式，返回完整 UI Spec
    POST /api/v1/api-catalog/index  重建 API Catalog 向量索引（管理端）
"""

from __future__ import annotations

import logging
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.models.schemas import (
    ApiQueryBusinessIntent,
    ApiQueryContextStepResult,
    ApiQueryDetailRequestRuntime,
    ApiQueryDetailRuntime,
    ApiQueryDetailSourceRuntime,
    ApiQueryExecutionErrorDetail,
    ApiQueryExecutionPlan,
    ApiQueryExecutionResult,
    ApiQueryExecutionStatus,
    ApiQueryFormFieldRuntime,
    ApiQueryFormOptionSourceRuntime,
    ApiQueryFormRuntime,
    ApiQueryFormSubmitRuntime,
    ApiQueryListFilterFieldRuntime,
    ApiQueryListFiltersRuntime,
    ApiQueryListPaginationRuntime,
    ApiQueryListQueryContextRuntime,
    ApiQueryListRuntime,
    ApiQueryMode,
    ApiQueryPatchContext,
    ApiQueryPatchTrigger,
    ApiQueryRequest,
    ApiQueryResponseMode,
    ApiQueryResponse,
    ApiQueryRoutingResult,
    ApiQueryRuntimeMetadataResponse,
    ApiQueryUIAction,
    ApiQueryUIRuntime,
)
from app.services.api_catalog.executor import ApiExecutor
from app.services.api_catalog.dag_executor import ApiDagExecutor, DagExecutionReport, DagStepExecutionRecord
from app.services.api_catalog.dag_planner import ApiDagPlanner, DagPlanValidationError, build_single_step_plan
from app.services.api_catalog.business_intents import (
    NOOP_BUSINESS_INTENT,
    get_business_intent_catalog_service,
    normalize_business_intent_codes,
    resolve_business_intent_risk_level,
)
from app.services.api_catalog.registry_source import ApiCatalogRegistrySource, ApiCatalogSourceError
from app.services.api_catalog.schema import ApiCatalogEntry, ApiCatalogSearchFilters
from app.services.api_catalog.param_extractor import ApiParamExtractor
from app.services.api_catalog.retriever import ApiCatalogRetriever
from app.services.api_query_llm_service import ApiQueryLLMService
from app.services.api_query_response_builder import ApiQueryResponseBuilder
from app.services.api_query_state import (
    ApiQueryRuntimeContext,
    ApiQueryState,
    build_execution_state,
    summarize_route_hint,
)
from app.services.api_query_workflow import ApiQueryWorkflow
from app.services.dynamic_ui_service import DynamicUIService, UISpecBuildResult
from app.services.ui_spec_guard import UISpecValidationResult
from app.services.ui_catalog_service import UICatalogService
from app.services.ui_snapshot_service import UISnapshotService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api-query", tags=["API Query"])

# ── 单例（避免每次请求重建 embedding model）──────────────────────
_retriever: ApiCatalogRetriever | None = None
_extractor: ApiParamExtractor | None = None
_executor: ApiExecutor | None = None
_planner: ApiDagPlanner | None = None
_dynamic_ui: DynamicUIService | None = None
_ui_catalog: UICatalogService | None = None
_snapshot_service: UISnapshotService | None = None
_registry_source: ApiCatalogRegistrySource | None = None
_api_query_llm: ApiQueryLLMService | None = None
_workflow: ApiQueryWorkflow | None = None
_bearer = HTTPBearer(auto_error=False)
_QUERY_SAFE_METHODS = {"GET", "POST"}
_QUERY_PARAM_SOURCE_BY_METHOD = {"GET": "queryParams", "POST": "body"}
_LIST_FILTER_EXCLUDED_FIELDS = {"id", "page", "pageNum", "pageSize", "size", "limit"}
_PATCH_PAGE_SIZE_MAX = 50
# 这里固定保留 5 条是为了给 Renderer 足够上下文，又避免把大结果集整包塞进生成链路导致注意力失焦。
_CONTEXT_ROW_LIMIT = 5


def _get_services() -> tuple[ApiCatalogRetriever, ApiParamExtractor, ApiExecutor, DynamicUIService, UISnapshotService]:
    """获取 `api_query` 所需的单例服务。"""
    global _retriever, _extractor, _executor, _dynamic_ui, _snapshot_service
    if _retriever is None:
        _retriever = ApiCatalogRetriever()
    if _extractor is None:
        _extractor = ApiParamExtractor(llm_service=_get_api_query_llm_service())
    if _executor is None:
        _executor = ApiExecutor()
    if _dynamic_ui is None:
        _dynamic_ui = DynamicUIService(
            catalog_service=_get_ui_catalog_service(),
            llm_service=_get_api_query_llm_service(),
        )
    if _snapshot_service is None:
        _snapshot_service = UISnapshotService()
    return _retriever, _extractor, _executor, _dynamic_ui, _snapshot_service


def _get_api_query_llm_service() -> ApiQueryLLMService:
    """获取 `/api_query` 专用 LLM 单例。

    功能：
        第二、三、五阶段必须共享同一模型配置，否则轻量路由、Planner 和 Renderer
        可能分别命中不同后端，导致同一请求在阶段间出现风格漂移甚至结构不兼容。
    """
    global _api_query_llm
    if _api_query_llm is None:
        _api_query_llm = ApiQueryLLMService()
    return _api_query_llm


def _get_ui_catalog_service() -> UICatalogService:
    """获取 UI 目录单例。

    功能：
        `api_query` 路由与 `DynamicUIService` 必须共享同一份进程内目录快照，否则
        `runtime-metadata`、Renderer Prompt 和最终 `ui_runtime` 很容易各说各话。
    """
    global _ui_catalog
    if _ui_catalog is None:
        _ui_catalog = UICatalogService()
    return _ui_catalog


def _get_planner() -> ApiDagPlanner:
    """获取第三阶段 Planner 单例。"""
    global _planner
    if _planner is None:
        _planner = ApiDagPlanner(llm_service=_get_api_query_llm_service())
    return _planner


def _get_registry_source() -> ApiCatalogRegistrySource:
    """获取 API Catalog 注册表源单例。

    功能：
        `direct` 快路需要按 `api_id` 精确命中元数据，但不值得为每次详情/分页请求
        都新建一次 MySQL 连接池。这里和其他 gateway 服务保持相同的进程级复用策略。
    """
    global _registry_source
    if _registry_source is None:
        _registry_source = ApiCatalogRegistrySource()
    return _registry_source


def _get_response_builder() -> ApiQueryResponseBuilder:
    """获取 `/api-query` 响应收口器单例。

    功能：
        Wave 1 先把响应拼装从 route 中抽离，但这里不做额外缓存。这样测试替身、热重载
        和后续 workflow 注入都能稳定拿到当前请求视角下的依赖装配结果。
    """
    _, _, _, dynamic_ui, snapshot_service = _get_services()
    return ApiQueryResponseBuilder(
        dynamic_ui=dynamic_ui,
        snapshot_service=snapshot_service,
        ui_catalog_service=_get_ui_catalog_service(),
        registry_source=_get_registry_source(),
    )


def _get_workflow() -> ApiQueryWorkflow:
    """获取 `/api-query` 外层工作流单例。

    功能：
        工作流图需要编译复用，但测试又会 monkeypatch route 级 getter。这里通过 lambda 延迟
        读取当前模块的 getter，保证单例 graph 与动态替身装配可以同时成立。
    """
    global _workflow
    if _workflow is None:
        _workflow = ApiQueryWorkflow(
            services_getter=lambda: _get_services(),
            planner_getter=lambda: _get_planner(),
            response_builder_getter=lambda: _get_response_builder(),
            registry_source_getter=lambda: _get_registry_source(),
            allowed_business_intent_codes_getter=lambda: _get_route_allowed_business_intent_codes(),
        )
    return _workflow


# ── 请求 / 响应 Schema ───────────────────────────────────────────


# ── 主接口：自然语言 → 数据 + UI ────────────────────────────────


@router.post("", response_model=ApiQueryResponse, summary="业务接口查询（支持自然语言与直达模式）")
async def api_query(
    request_body: ApiQueryRequest,
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> ApiQueryResponse:
    """
    用户自然语言输入 → 语义匹配业务接口 → 调用接口 → 返回 json-render UI Spec。

    流程：
    1. 轻量路由先提取 `query_domains + business_intents`
    2. 按业务域执行分层召回，避免全域 Top-K 偏科
    3. 在候选集内完成最终接口选择 + 参数提取
    4. 透传 Token 调用 business-server
    5. 响应规范化 → DynamicUIService → UI Spec
    """
    trace_id = _resolve_trace_id(request)
    interaction_id = _resolve_interaction_id(request)
    conversation_id = _resolve_conversation_id(request_body)
    user_context = _extract_user_context(request)
    log_prefix = _build_api_query_log_prefix(trace_id, interaction_id, conversation_id)

    # 用户 token（透传给 business-server）
    user_token = f"Bearer {credentials.credentials}" if credentials else None
    logger.info("%s dispatch mode=%s", log_prefix, request_body.mode.value)
    return await _get_workflow().run(
        request_body,
        trace_id=trace_id,
        interaction_id=interaction_id,
        conversation_id=conversation_id,
        user_context=user_context,
        user_token=user_token,
    )


@router.get("/runtime-metadata", response_model=ApiQueryRuntimeMetadataResponse, summary="获取 api_query 运行时元数据")
async def get_runtime_metadata() -> ApiQueryRuntimeMetadataResponse:
    """返回 api_query 对外暴露的业务意图 / UI 运行时契约。"""
    catalog_service = _get_ui_catalog_service()
    # 这里主动预热目录，是为了让运营侧最先看到 MySQL 中维护的真实组件/动作说明。
    await catalog_service.warmup()
    return ApiQueryRuntimeMetadataResponse(
        ui_runtime=ApiQueryUIRuntime(
            components=catalog_service.get_component_codes(intent="query"),
            ui_actions=catalog_service.build_runtime_actions(),
            list=ApiQueryListRuntime(
                enabled=False,
                route_url="/api/v1/api-query",
                ui_action="remoteQuery",
                param_source="queryParams",
                pagination=ApiQueryListPaginationRuntime(
                    enabled=False,
                    page_param="pageNum",
                    page_size_param="pageSize",
                ),
                filters=ApiQueryListFiltersRuntime(enabled=False),
                query_context=ApiQueryListQueryContextRuntime(
                    enabled=False,
                    page_param="pageNum",
                    page_size_param="pageSize",
                ),
            ),
            detail=ApiQueryDetailRuntime(
                enabled=False,
                route_url="/api/v1/api-query",
                ui_action="remoteQuery",
                request=ApiQueryDetailRequestRuntime(
                    param_source="queryParams",
                ),
                source=ApiQueryDetailSourceRuntime(),
            ),
            form=ApiQueryFormRuntime(
                enabled=False,
                route_url="/api/v1/api-query",
                ui_action="remoteMutation",
            ),
        ),
        template_scenarios=catalog_service.get_template_scenarios(),
    )


@router.post("/catalog/index", summary="重建 API Catalog 向量索引（管理端）")
async def rebuild_catalog_index() -> dict[str, Any]:
    """从业务 MySQL 重新入库所有接口到 Milvus。"""
    from app.services.api_catalog.indexer import ApiCatalogIndexer

    indexer = ApiCatalogIndexer()
    result = await indexer.index_all()
    return result


# ── 辅助函数 ─────────────────────────────────────────────────────


def _extract_user_context(request: Request) -> dict[str, Any]:
    """从请求中提取可自动填充的上下文（如 user_id）。

    业务接口通常需要 userId 等参数，从 JWT 解码后注入，
    避免用户每次都要手动说"我的 ID 是 xxx"。
    """
    ctx: dict[str, Any] = {}
    identity = getattr(request.state, "identity", None)
    if identity is not None and hasattr(identity, "to_request_context"):
        for key, value in identity.to_request_context().items():
            if value not in (None, "", [], {}):
                ctx[key] = value
    elif hasattr(request.state, "user_id"):
        ctx["userId"] = request.state.user_id
    return ctx


def _summarize_request_query(request_body: ApiQueryRequest) -> str:
    """生成适合日志与审计的请求摘要。

    功能：
        `direct` 模式本来就没有自然语言 query；这里主动收敛成“模式 + 关键锚点”，
        避免日志系统里再次出现 `None[:100]` 这类无意义异常，也方便区分慢链路和快链路。
    """
    if request_body.mode == ApiQueryMode.DIRECT and request_body.direct_query is not None:
        return f"direct:{request_body.direct_query.api_id}"
    return (request_body.query or "")[:100]


def _resolve_trace_id(request: Request) -> str:
    """优先复用外部 Trace ID，缺失时由网关生成。"""
    header_trace_id = request.headers.get("X-Trace-Id") or request.headers.get("X-Request-Id")
    return header_trace_id or uuid4().hex


def _resolve_interaction_id(request: Request) -> str | None:
    """提取前端透传的交互 ID。

    功能：
        `interaction_id` 用来串起一次用户连续操作内的多次请求，例如“打开列表 -> 查看详情 ->
        提交确认”。网关这里不负责生成，只做透传与回显，避免和 `trace_id` 的单请求语义混淆。

    Args:
        request: 当前 FastAPI 请求对象。

    Returns:
        头部中的 `X-Interaction-Id`；空字符串会被折叠为 `None`。

    Edge Cases:
        - 前端未传时返回 `None`，不自行兜底生成
        - 仅做首尾空白裁剪，不在网关层擅自改写业务方生成的 ID
    """
    header_interaction_id = (request.headers.get("X-Interaction-Id") or "").strip()
    return header_interaction_id or None


def _resolve_conversation_id(request_body: ApiQueryRequest) -> str | None:
    """提取前端传入的会话 ID。

    功能：
        `conversation_id` 描述的是一段多轮业务会话，而不是单次点击。把它放进日志链路后，
        运维可以把“列表 -> 详情 -> 下一步查询”这类连续请求聚成一条业务上下文，而不必只靠
        多个 `trace_id` 人工拼接。

    Args:
        request_body: `/api-query` 当前请求体。

    Returns:
        请求体中的 `conversation_id`；空字符串和全空白会被折叠为 `None`。

    Edge Cases:
        - 前端未传时返回 `None`，网关不擅自生成，以免篡改业务会话语义
        - 只做空白裁剪，保留前端定义的原始 ID 形态，方便跨端对账
    """
    conversation_id = (request_body.conversation_id or "").strip()
    return conversation_id or None


def _build_api_query_log_prefix(
    trace_id: str,
    interaction_id: str | None,
    conversation_id: str | None,
) -> str:
    """统一构造 `api_query` 日志前缀。

    功能：
        该接口已经长期依赖 `trace_id` 做单请求排障；本次补入 `interaction_id` 的目标，是让
        运维可以把同一次用户操作拆出来看；继续补入 `conversation_id`，则是为了把多轮问答
        串成同一业务会话，避免列表页和详情页日志只能看见零散请求切片。
    """
    return f"api_query[trace={trace_id} interaction={interaction_id or '-'} conversation={conversation_id or '-'}]"


def _format_query_domains_for_response(query_domains: list[str]) -> list[str]:
    """将内部 domain 编码转换成对外稳定展示格式。

    功能：
        检索链路内部继续使用小写编码，便于和 Milvus 标量字段对齐；
        对外响应则统一转成大写，和技术方案中的展示契约保持一致。
    """
    return [_format_domain_for_response(domain) for domain in query_domains if domain]


def _format_domain_for_response(domain: str | None) -> str:
    """格式化单个业务域编码。"""
    normalized = (domain or "").strip()
    return normalized.upper() if normalized else ""


def _dedupe_non_empty(values: list[str]) -> list[str]:
    """对过滤入参做去空与去重，避免把脏值直接推进 Milvus 表达式。"""
    deduped: list[str] = []
    for value in values:
        if not value or value in deduped:
            continue
        deduped.append(value)
    return deduped


def _ensure_query_safe_entry(
    entry: ApiCatalogEntry,
    trace_id: str,
    interaction_id: str | None = None,
    conversation_id: str | None = None,
) -> None:
    """强制拦截非查询安全接口。

    功能：
        `/api-query` 的安全边界已经从“只允许 GET”升级为“只允许显式标记为查询语义的接口”。
        因此这里同时校验 `operation_safety=query` 和 `method in {GET, POST}`，把 mutation 接口
        尽量拦在候选刚被选中的第一时间。
    """
    if entry.operation_safety == "mutation":
        logger.warning(
            "%s blocked non-query-safe endpoint id=%s safety=%s method=%s path=%s",
            _build_api_query_log_prefix(trace_id, interaction_id, conversation_id),
            entry.id,
            entry.operation_safety,
            entry.method,
            entry.path,
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"[{trace_id}] api_query 仅支持查询安全接口，当前接口语义为 {entry.operation_safety}",
        )

    if entry.method in _QUERY_SAFE_METHODS:
        return
    logger.warning(
        "%s blocked non-query-method endpoint id=%s method=%s path=%s",
        _build_api_query_log_prefix(trace_id, interaction_id, conversation_id),
        entry.id,
        entry.method,
        entry.path,
    )
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=f"[{trace_id}] api_query 仅支持 GET/POST 查询接口，当前命中 {entry.method} {entry.path}",
    )


def _ensure_active_entry(
    entry: ApiCatalogEntry,
    *,
    trace_id: str,
    interaction_id: str | None = None,
    conversation_id: str | None = None,
) -> None:
    """拦截未激活目录项，保持 `direct` 与召回链路的一致安全边界。

    功能：
        `nl` 模式默认通过 `status=active` 做 Milvus 标量过滤；`direct` 模式绕过召回后，
        必须在这里补上相同的治理红线，避免前端通过已下线接口 ID 直接穿透执行。
    """
    if entry.status == "active":
        return
    logger.warning(
        "%s blocked inactive endpoint id=%s status=%s path=%s",
        _build_api_query_log_prefix(trace_id, interaction_id, conversation_id),
        entry.id,
        entry.status,
        entry.path,
    )
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=f"[{trace_id}] direct 模式仅允许调用激活接口，当前接口状态为 {entry.status}",
    )


def _validate_direct_query_params(
    entry: ApiCatalogEntry,
    params: dict[str, Any],
    *,
    trace_id: str,
    interaction_id: str | None,
    conversation_id: str | None,
) -> dict[str, Any]:
    """校验 `direct` 模式的显式参数。

    功能：
        机器构造的快路请求不应该再沿用自然语言链路的“尽量猜”策略。这里严格执行：

        1. 参数名必须命中 schema
        2. required 字段必须齐全

        这样一旦前端拼错字段，就会在网关入口被立刻显式暴露，而不是静默打到业务系统。

    Returns:
        原样返回通过校验的参数字典，供执行计划直接复用。

    Raises:
        HTTPException: 当出现未声明参数或缺失必填参数时抛出 422。
    """
    declared_fields = set(entry.param_schema.properties.keys())
    unknown_fields = [field for field in params if field not in declared_fields]
    if unknown_fields:
        logger.warning(
            "%s direct params rejected id=%s unknown_fields=%s",
            _build_api_query_log_prefix(trace_id, interaction_id, conversation_id),
            entry.id,
            unknown_fields,
        )
        _raise_direct_query_error(
            trace_id=trace_id,
            detail=f"direct 模式存在未声明参数：{', '.join(unknown_fields)}",
        )

    missing_required_params = _find_missing_required_params(entry, params)
    if missing_required_params:
        logger.warning(
            "%s direct params rejected id=%s missing_required=%s",
            _build_api_query_log_prefix(trace_id, interaction_id, conversation_id),
            entry.id,
            missing_required_params,
        )
        _raise_direct_query_error(
            trace_id=trace_id,
            detail=f"direct 模式缺少必要参数：{', '.join(missing_required_params)}",
        )

    return dict(params)


def _validate_direct_patch_request(
    request_body: ApiQueryRequest,
    entry: ApiCatalogEntry,
    params: dict[str, Any],
    *,
    trace_id: str,
    interaction_id: str | None,
    conversation_id: str | None,
) -> None:
    """校验列表 patch 快路的专属约束。

    功能：
        `mode=direct` 只是说明“不再走自然语言链路”，并不代表任何直达请求都适合返回 patch。
        这里把设计文档里对 patch 模式的硬边界收口成确定性校验：

        1. 只能用于单步只读列表接口
        2. 只能用于开启了分页 hint 的 GET 接口
        3. `pageSize` 必须受上限保护
        4. 改筛选条件时必须显式回到第一页

    Raises:
        HTTPException: 当 patch 请求违反运行时契约时抛出 422。
    """
    if request_body.response_mode != ApiQueryResponseMode.PATCH:
        return

    log_prefix = _build_api_query_log_prefix(trace_id, interaction_id, conversation_id)
    pagination_hint = entry.pagination_hint
    if entry.method != "GET" or not pagination_hint.enabled:
        logger.warning("%s direct patch rejected id=%s reason=unsupported_entry", log_prefix, entry.id)
        _raise_direct_query_error(
            trace_id=trace_id,
            detail="PATCH_MODE_NOT_SUPPORTED: 当前接口不是开启分页能力的只读 GET 列表接口",
        )

    page_param = pagination_hint.page_param or "pageNum"
    page_size_param = pagination_hint.page_size_param or "pageSize"
    missing_pagination_params = [param_name for param_name in (page_param, page_size_param) if param_name not in params]
    if missing_pagination_params:
        logger.warning(
            "%s direct patch rejected id=%s missing_pagination_params=%s",
            log_prefix,
            entry.id,
            missing_pagination_params,
        )
        _raise_direct_query_error(
            trace_id=trace_id,
            detail=f"PATCH_MODE_NOT_SUPPORTED: patch 模式必须显式提供分页参数：{', '.join(missing_pagination_params)}",
        )

    page_size_value = params.get(page_size_param)
    if isinstance(page_size_value, (int, float)) and int(page_size_value) > _PATCH_PAGE_SIZE_MAX:
        logger.warning(
            "%s direct patch rejected id=%s page_size=%s over_limit=%s",
            log_prefix,
            entry.id,
            page_size_value,
            _PATCH_PAGE_SIZE_MAX,
        )
        _raise_direct_query_error(
            trace_id=trace_id,
            detail=f"patch 模式下 {page_size_param} 不能超过 {_PATCH_PAGE_SIZE_MAX}",
        )

    patch_context = request_body.patch_context
    if patch_context is None:
        return

    if patch_context.trigger in {ApiQueryPatchTrigger.FILTER_SUBMIT, ApiQueryPatchTrigger.FILTER_RESET}:
        page_value = params.get(page_param)
        if page_value != 1:
            logger.warning(
                "%s direct patch rejected id=%s trigger=%s invalid_page_reset=%s",
                log_prefix,
                entry.id,
                patch_context.trigger.value,
                page_value,
            )
            _raise_direct_query_error(
                trace_id=trace_id,
                detail=f"patch 模式下触发 {patch_context.trigger.value} 时必须将 {page_param} 重置为 1",
            )


def _build_direct_query_text(entry: ApiCatalogEntry, params: dict[str, Any]) -> str:
    """为快路构造稳定的渲染上下文文本。

    功能：
        `direct` 模式没有自然语言 query，但第五阶段仍需要一段可追踪的 `user_query`
        来参与标题、日志和冻结视图说明。这里用“接口描述 + 关键参数”生成一个稳定摘要。
    """
    if not params:
        return f"直达查询：{entry.description}"
    param_keys = ", ".join(sorted(params.keys()))
    return f"直达查询：{entry.description}（参数：{param_keys}）"


def _raise_direct_query_error(*, trace_id: str, detail: str) -> None:
    """统一抛出 `direct` 模式的 422 错误。

    功能：
        快路失败不允许偷偷回退到自然语言模式；这里统一返回结构化 422，
        让前端和联调日志都能明确感知是“快路契约错误”，而不是网关随机降级。
    """
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=f"[{trace_id}] {detail}",
    )


def _build_business_intents(intent_codes: list[str]) -> list[ApiQueryBusinessIntent]:
    """将业务意图编码转换为对外响应对象。

    功能：
        第二阶段内部允许保留历史别名，但对外响应必须收敛成设计文档中的稳定业务语义。

    Args:
        intent_codes: 第二阶段原始业务意图编码，可能混入历史别名或旧版只读编码。

    Returns:
        归一化后的业务意图对象列表；同一 canonical code 只保留一份。

    Edge Cases:
        - 历史高风险别名会被折叠成 canonical code，同时保留 `risk_level=high`
        - 纯读旧编码会统一折叠为 `none`
    """
    intent_catalog = get_business_intent_catalog_service()
    codes = _normalize_business_intent_codes(intent_codes)
    business_intents: list[ApiQueryBusinessIntent] = []
    for code in dict.fromkeys(codes):
        definition = intent_catalog.get_definition(code)
        if definition is None or not definition.enabled or not definition.allow_in_response:
            continue
        business_intents.append(
            ApiQueryBusinessIntent(
                code=code,
                name=definition.name,
                category="write" if definition.category == "write" else "read",
                description=definition.description,
                risk_level=resolve_business_intent_risk_level(code, intent_codes),
            )
        )

    if business_intents:
        return business_intents

    fallback_definition = intent_catalog.get_definition(NOOP_BUSINESS_INTENT)
    if fallback_definition is None:
        return []
    return [
        ApiQueryBusinessIntent(
            code=fallback_definition.code,
            name=fallback_definition.name,
            category="write" if fallback_definition.category == "write" else "read",
            description=fallback_definition.description,
            risk_level=resolve_business_intent_risk_level(fallback_definition.code, intent_codes),
        )
    ]


def _normalize_business_intent_codes(intent_codes: list[str]) -> list[str]:
    """把历史别名与旧只读编码折叠成稳定业务意图。

    功能：
        文档层已经把第二阶段语义收敛为 `saveToServer / deleteCustomer / none`，
        这里负责吸收旧 Prompt、旧 catalog 与高风险别名的历史债务，避免外部契约继续漂移。
    """
    return normalize_business_intent_codes(intent_codes)


def _get_route_allowed_business_intent_codes() -> set[str]:
    """读取第二阶段 Router 白名单。

    功能：
        白名单来源已经迁移到业务意图目录服务，路由层不再维护模块级硬编码 set，
        避免 MySQL 配置、Prompt 注入和响应契约继续各自漂移。
    """
    return get_business_intent_catalog_service().get_allowed_codes()


def _build_runtime_actions(action_codes: set[str] | None = None) -> list[ApiQueryUIAction]:
    """按当前运行时启用状态构造 UI 动作定义。

    功能：
        动作目录已经迁移到 `UICatalogService` 统一治理，路由层只保留“当前请求开放哪些动作”
        这一层决策，避免组件目录和运行时开关继续写死在文件内。
    """
    return _get_ui_catalog_service().build_runtime_actions(action_codes)


def _infer_param_source(method: str | None) -> str:
    """推导当前接口参数的承载位置。

    功能：
        前端二跳不应该自己猜“同样一个 params 最终该进 query string 还是 body”。
        这里把 HTTP 方法到参数归属的约定固定在网关里，保证详情、分页和后续表单契约
        使用同一份事实。
    """
    normalized_method = (method or "GET").strip().upper()
    return _QUERY_PARAM_SOURCE_BY_METHOD.get(normalized_method, "queryParams")


def _normalize_runtime_value_type(schema_type: Any, *, fallback_value: Any = None) -> str:
    """把 schema 类型压成前端运行时契约可消费的轻量值类型。"""
    normalized_type = str(schema_type or "").strip().lower()
    if normalized_type in {"string", "number", "integer", "boolean", "array", "object"}:
        return "number" if normalized_type == "integer" else normalized_type

    if isinstance(fallback_value, bool):
        return "boolean"
    if isinstance(fallback_value, (int, float)):
        return "number"
    if isinstance(fallback_value, list):
        return "array"
    if isinstance(fallback_value, dict):
        return "object"
    return "string"


def _build_list_filter_fields(
    entry: ApiCatalogEntry,
    *,
    page_param: str | None,
    page_size_param: str | None,
) -> list[ApiQueryListFilterFieldRuntime]:
    """根据目录参数 schema 推导列表筛选字段。

    功能：
        筛选字段本质上是“允许前端继续提交哪些查询参数”。这里优先信任目录 schema，
        再排除分页字段和网关保留字段，避免前端误把保留协议当成业务筛选条件展示出去。
    """
    excluded_fields = set(_LIST_FILTER_EXCLUDED_FIELDS)
    if page_param:
        excluded_fields.add(page_param)
    if page_size_param:
        excluded_fields.add(page_size_param)

    filter_fields: list[ApiQueryListFilterFieldRuntime] = []
    required_fields = set(entry.param_schema.required)
    for field_name, field_schema in entry.param_schema.properties.items():
        if field_name in excluded_fields:
            continue

        label = (
            str(field_schema.get("title") or "").strip() or str(field_schema.get("label") or "").strip() or field_name
        )
        filter_fields.append(
            ApiQueryListFilterFieldRuntime(
                name=field_name,
                label=label,
                value_type=_normalize_runtime_value_type(field_schema.get("type")),
                required=field_name in required_fields,
            )
        )
    return filter_fields


def _has_write_business_intent(business_intents: list[ApiQueryBusinessIntent]) -> bool:
    """判断当前请求是否存在合法写意图。"""
    return any(intent.category == "write" and intent.code != NOOP_BUSINESS_INTENT for intent in business_intents)


def _build_ui_runtime(
    entry: ApiCatalogEntry,
    execution_result: ApiQueryExecutionResult,
    *,
    params: dict[str, Any],
    business_intents: list[ApiQueryBusinessIntent],
) -> ApiQueryUIRuntime:
    """根据接口元数据和执行结果推导前端运行时契约。

    功能：
        这层要解决两个长期漂移问题：
        1. 把列表、详情、表单的二跳能力统一上移到 `ui_runtime`
        2. 不再让前端从 `execution_plan` 或 UI 组件树里反向猜交互契约
    """
    rows = _normalize_rows(execution_result.data)
    action_codes = {"refresh", "export"}
    requested_component_codes = ["PlannerCard", "PlannerTable", "PlannerDetailCard", "PlannerNotice"]
    if _has_write_business_intent(business_intents):
        requested_component_codes.extend(["PlannerForm", "PlannerInput", "PlannerSelect", "PlannerButton"])
    components = _get_ui_catalog_service().get_component_codes(
        intent="query",
        requested_codes=requested_component_codes,
    )
    param_source = _infer_param_source(entry.method)

    detail_hint = entry.detail_hint
    identifier_field = detail_hint.identifier_field or _infer_identifier_field(rows)
    detail_enabled = (
        execution_result.status == ApiQueryExecutionStatus.SUCCESS
        and bool(identifier_field)
        and (detail_hint.enabled or identifier_field is not None)
    )

    pagination_hint = entry.pagination_hint
    page_param = pagination_hint.page_param or "pageNum"
    page_size_param = pagination_hint.page_size_param or "pageSize"
    filter_fields = _build_list_filter_fields(
        entry,
        page_param=page_param,
        page_size_param=page_size_param,
    )
    is_list_payload = isinstance(execution_result.data, list)
    pagination_enabled = (
        execution_result.status in {ApiQueryExecutionStatus.SUCCESS, ApiQueryExecutionStatus.EMPTY}
        and (pagination_hint.enabled or execution_result.total > len(rows))
        and (execution_result.total > 0 or bool(rows))
    )
    list_enabled = execution_result.status in {
        ApiQueryExecutionStatus.SUCCESS,
        ApiQueryExecutionStatus.EMPTY,
    } and (is_list_payload or pagination_enabled or bool(filter_fields))

    if detail_enabled or list_enabled:
        action_codes.add("remoteQuery")
    if detail_enabled:
        action_codes.add("view_detail")
    if _has_write_business_intent(business_intents):
        action_codes.add("remoteMutation")

    current_params = dict(params)
    preserve_on_pagination = [
        field_name for field_name in current_params if field_name not in {page_param, page_size_param, "id"}
    ]
    list_api_id = pagination_hint.api_id or entry.id

    return ApiQueryUIRuntime(
        components=components,
        ui_actions=_build_runtime_actions(action_codes),
        list=ApiQueryListRuntime(
            enabled=list_enabled,
            api_id=list_api_id if list_enabled else None,
            route_url="/api/v1/api-query" if list_enabled else None,
            ui_action=(pagination_hint.ui_action or "remoteQuery") if list_enabled else None,
            param_source=param_source if list_enabled else None,
            pagination=ApiQueryListPaginationRuntime(
                enabled=pagination_enabled,
                total=execution_result.total,
                page_size=_infer_page_size(params, len(rows)),
                current_page=_infer_current_page(params),
                page_param=page_param if list_enabled else None,
                page_size_param=page_size_param if list_enabled else None,
                mutation_target=pagination_hint.mutation_target if pagination_enabled else None,
            ),
            filters=ApiQueryListFiltersRuntime(
                enabled=bool(filter_fields),
                fields=filter_fields,
            ),
            query_context=ApiQueryListQueryContextRuntime(
                enabled=list_enabled,
                current_params=current_params,
                page_param=page_param if list_enabled else None,
                page_size_param=page_size_param if list_enabled else None,
                preserve_on_pagination=preserve_on_pagination,
                reset_page_on_filter_change=True,
            ),
        ),
        detail=ApiQueryDetailRuntime(
            enabled=detail_enabled,
            api_id=(detail_hint.api_id or entry.id) if detail_enabled else None,
            route_url="/api/v1/api-query" if detail_enabled else None,
            ui_action=(detail_hint.ui_action or "remoteQuery") if detail_enabled else None,
            request=ApiQueryDetailRequestRuntime(
                param_source=param_source if detail_enabled else None,
                identifier_param=(detail_hint.query_param or identifier_field) if detail_enabled else None,
            ),
            source=ApiQueryDetailSourceRuntime(
                identifier_field=identifier_field if detail_enabled else None,
                value_type=(
                    _normalize_runtime_value_type(
                        None,
                        fallback_value=rows[0].get(identifier_field) if rows and identifier_field else None,
                    )
                    if detail_enabled
                    else None
                ),
                required=detail_enabled,
            ),
        ),
    )


async def _enrich_runtime_from_ui_spec(
    runtime: ApiQueryUIRuntime,
    ui_spec: dict[str, Any] | None,
    *,
    business_intents: list[ApiQueryBusinessIntent],
    trace_id: str,
) -> ApiQueryUIRuntime:
    """根据最终 `ui_spec` 反推表单提交契约。

    功能：
        列表和详情二跳主要来自目录 hint；表单提交则不同，真正的提交按钮、payload 绑定
        和目标 `api_id` 只有在第五阶段输出 Spec 后才真正落定。因此这里选择“以最终 Spec
        为准”，避免路由层提前拍脑袋猜一个错误的表单提交目标。
    """
    form_contract = await _extract_form_runtime_from_spec(
        ui_spec,
        business_intents=business_intents,
        trace_id=trace_id,
    )
    if not form_contract.enabled:
        return runtime
    return runtime.model_copy(update={"form": form_contract})


async def _extract_form_runtime_from_spec(
    ui_spec: dict[str, Any] | None,
    *,
    business_intents: list[ApiQueryBusinessIntent],
    trace_id: str,
) -> ApiQueryFormRuntime:
    """从最终 Spec 中提取表单运行时契约。

    功能：
        `ui_runtime.form` 的职责是告诉前端“往哪提、提什么”。这类信息如果继续散落在
        `PlannerButton.on.press.params` 里，前端每做一个表单都得重新解析组件树。

    Edge Cases:
        - 若页面不存在 `remoteMutation` 动作，则直接返回 disabled，避免给纯查询页挂空表单
        - 若 Renderer 给出了提交动作但目录里没有对应 mutation 接口，仍保留基础契约，
          避免为了补充类型信息把整页表单能力吞掉
    """
    write_intent = next(
        (intent for intent in business_intents if intent.category == "write" and intent.code != NOOP_BUSINESS_INTENT),
        None,
    )
    if write_intent is None or not _is_flat_ui_spec(ui_spec):
        return ApiQueryFormRuntime()

    mutation_action = _find_first_action_payload(ui_spec, target_action_code="remoteMutation")
    if mutation_action is None:
        return ApiQueryFormRuntime()

    action_params = mutation_action.get("params")
    if not isinstance(action_params, dict):
        return ApiQueryFormRuntime()

    api_id = action_params.get("api_id")
    payload = action_params.get("payload")
    if not isinstance(api_id, str) or not api_id.strip() or not isinstance(payload, dict):
        return ApiQueryFormRuntime()

    mutation_entry: ApiCatalogEntry | None = None
    try:
        mutation_entry = await _get_registry_source().get_entry_by_id(api_id)
    except Exception as exc:  # pragma: no cover - 依赖治理源状态的兜底分支
        logger.warning(
            "api_query[trace=%s] failed to enrich form mutation entry api_id=%s error=%s",
            trace_id,
            api_id,
            exc,
        )

    state = ui_spec.get("state") if isinstance(ui_spec, dict) else {}
    interactive_bindings = _collect_form_input_bindings(ui_spec)
    required_fields = set(mutation_entry.param_schema.required) if mutation_entry is not None else set()
    property_schemas = mutation_entry.param_schema.properties if mutation_entry is not None else {}

    form_fields: list[ApiQueryFormFieldRuntime] = []
    bind_paths: list[str] = []
    for submit_key, submit_value in payload.items():
        if not isinstance(submit_value, dict):
            continue
        state_path = submit_value.get("$bindState")
        if not isinstance(state_path, str) or not state_path.startswith("/"):
            continue

        bind_paths.append(state_path)
        binding_meta = interactive_bindings.get(state_path, {})
        component_type = binding_meta.get("component_type")
        source_kind = "user_input"
        writable = True
        if component_type == "PlannerSelect":
            source_kind = "dictionary"
        elif component_type is None:
            source_kind = "context"
            writable = False

        state_value = _read_state_value(state, state_path)
        field_schema = property_schemas.get(submit_key, {})
        form_fields.append(
            ApiQueryFormFieldRuntime(
                name=submit_key,
                value_type=_normalize_runtime_value_type(field_schema.get("type"), fallback_value=state_value),
                state_path=state_path,
                submit_key=submit_key,
                required=submit_key in required_fields,
                writable=writable,
                source_kind=source_kind,
                option_source=(binding_meta.get("option_source") if component_type == "PlannerSelect" else None),
            )
        )

    if not form_fields:
        return ApiQueryFormRuntime()

    return ApiQueryFormRuntime(
        enabled=True,
        form_code=f"{api_id}_form",
        mode=_infer_form_mode(form_fields),
        api_id=api_id,
        route_url="/api/v1/api-query",
        ui_action="remoteMutation",
        state_path=_infer_form_state_root(bind_paths),
        fields=form_fields,
        submit=ApiQueryFormSubmitRuntime(
            business_intent=write_intent.code,
            confirm_required=True,
        ),
    )


def _collect_form_input_bindings(ui_spec: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """收集表单输入组件的 `$bindState` 路径与字段来源元数据。

    功能：
        提交 payload 里只知道“从哪个 state_path 取值”，但不知道这个值是用户填写还是上下文透传。
        这里把输入组件类型和可推导的选项来源一起收集起来，后续即可稳定区分：

        1. 普通输入字段
        2. 字典下拉字段
        3. 仅用于透传的只读上下文字段
    """
    if not _is_flat_ui_spec(ui_spec):
        return {}

    bindings: dict[str, dict[str, Any]] = {}
    elements = ui_spec.get("elements")
    if not isinstance(elements, dict):
        return bindings

    for element in elements.values():
        if not isinstance(element, dict):
            continue
        component_type = element.get("type")
        if component_type not in {"PlannerInput", "PlannerSelect"}:
            continue
        props = element.get("props")
        if not isinstance(props, dict):
            continue
        value_binding = props.get("value")
        if isinstance(value_binding, dict):
            bind_state_path = value_binding.get("$bindState")
            if isinstance(bind_state_path, str) and bind_state_path.startswith("/"):
                bindings[bind_state_path] = {
                    "component_type": component_type,
                    "option_source": _extract_form_option_source(props.get("options")),
                }
    return bindings


def _extract_form_option_source(options_payload: Any) -> ApiQueryFormOptionSourceRuntime | None:
    """从 `PlannerSelect.props.options` 推导可复用的选项来源契约。

    功能：
        `ui_runtime.form.fields[*].option_source` 的目的不是复刻整段 options，而是告诉前端
        “这个下拉框的选项应该从哪类数据源拿”。这样二跳刷新或表单复用时，前端无需再次
        反向解析整棵组件树。

    Edge Cases:
        - 静态 options 列表只标记为 `static`，避免把具体枚举值重复塞进运行时契约
        - 只要识别不到稳定来源，就返回 `None`，不虚构字典编码
    """
    if isinstance(options_payload, list):
        return ApiQueryFormOptionSourceRuntime(type="static")
    if not isinstance(options_payload, dict):
        return None

    dict_code = options_payload.get("dict_code") or options_payload.get("dictCode")
    if isinstance(dict_code, str) and dict_code.strip():
        return ApiQueryFormOptionSourceRuntime(type="dict", dict_code=dict_code.strip())

    option_type = options_payload.get("type")
    if option_type == "dict":
        inferred_dict_code = options_payload.get("code") or options_payload.get("name")
        return ApiQueryFormOptionSourceRuntime(
            type="dict",
            dict_code=inferred_dict_code.strip()
            if isinstance(inferred_dict_code, str) and inferred_dict_code.strip()
            else None,
        )

    if isinstance(options_payload.get("$fromContext"), str):
        return ApiQueryFormOptionSourceRuntime(type="context")

    return None


def _find_first_action_payload(ui_spec: dict[str, Any], *, target_action_code: str) -> dict[str, Any] | None:
    """在 flat spec 中寻找首个指定动作对象。"""

    def walk(node: Any) -> dict[str, Any] | None:
        if isinstance(node, dict):
            action_code = node.get("action")
            node_type = node.get("type")
            if action_code == target_action_code or node_type == target_action_code:
                return node
            for child in node.values():
                matched = walk(child)
                if matched is not None:
                    return matched
        elif isinstance(node, list):
            for item in node:
                matched = walk(item)
                if matched is not None:
                    return matched
        return None

    return walk(ui_spec)


def _read_state_value(state: Any, state_path: str) -> Any:
    """按 `/form/goal` 形式读取当前 state 中的值。"""
    if not isinstance(state, dict) or not state_path.startswith("/"):
        return None

    current: Any = state
    for segment in [item for item in state_path.split("/") if item]:
        if not isinstance(current, dict) or segment not in current:
            return None
        current = current[segment]
    return current


def _infer_form_state_root(bind_paths: list[str]) -> str | None:
    """根据字段绑定路径推导表单根状态路径。"""
    if not bind_paths:
        return None

    segments_list = [[segment for segment in path.split("/") if segment] for path in bind_paths]
    if not segments_list:
        return None

    common_segments: list[str] = []
    for segment_group in zip(*segments_list):
        if len(set(segment_group)) != 1:
            break
        common_segments.append(segment_group[0])

    # 只有单字段时，完整路径会把叶子节点也算进公共前缀。
    # 这里主动退回一层，避免把 `/form/customerId` 误报成表单根路径。
    if len(common_segments) == len(segments_list[0]) and len(common_segments) > 1:
        common_segments = common_segments[:-1]

    if not common_segments:
        return None
    return "/" + "/".join(common_segments)


def _infer_form_mode(fields: list[ApiQueryFormFieldRuntime]) -> str:
    """根据字段可编辑性推导表单模式。"""
    writable_fields = [field for field in fields if field.writable]
    if not writable_fields:
        return "confirm"
    if any(not field.writable for field in fields):
        return "edit"
    return "create"


def _finalize_ui_runtime(
    base_runtime: ApiQueryUIRuntime,
    ui_spec: dict[str, Any] | None,
) -> ApiQueryUIRuntime:
    """用最终生成的 UI Spec 回填组件与动作清单。

    功能：
        第五阶段正在从旧树形 Spec 迁移到 flat spec。这里统一从最终返回给前端的
        `ui_spec` 反推组件与动作，避免运行时元数据和真实 Spec 再次漂移。
    """
    action_codes = {action.code for action in base_runtime.ui_actions}
    action_codes.update(_collect_action_types(ui_spec))
    components = _collect_component_types(ui_spec) or base_runtime.components
    return base_runtime.model_copy(
        update={
            "components": components,
            "ui_actions": _build_runtime_actions(action_codes),
        }
    )


def _finalize_render_runtime(
    base_runtime: ApiQueryUIRuntime,
    ui_spec: dict[str, Any] | None,
    build_result: UISpecBuildResult,
) -> ApiQueryUIRuntime:
    """根据第五阶段结果收口最终运行时契约。

    功能：
        正常渲染时继续按 Spec 回填组件和动作；一旦触发 Guard 冻结，则主动清空交互能力，
        避免前端在“安全提示页”上仍然暴露详情、分页或潜在写动作。
    """
    finalized_runtime = _finalize_ui_runtime(base_runtime, ui_spec)
    if not build_result.frozen:
        return finalized_runtime

    components = _collect_component_types(ui_spec) or ["PlannerCard", "PlannerNotice"]
    return finalized_runtime.model_copy(
        update={
            "components": components,
            "ui_actions": [],
            "list": ApiQueryListRuntime(),
            "detail": ApiQueryDetailRuntime(),
            "form": ApiQueryFormRuntime(),
        }
    )


def _collect_component_types(node: Any) -> list[str]:
    """递归收集 UI Spec 中出现的组件类型。

    功能：
        同时兼容旧树形 Spec 和 `root/state/elements` 新协议，确保任务 1 切换契约后，
        `ui_runtime.components` 仍然能如实反映最终下发给前端的组件目录。
    """
    component_types: set[str] = set()

    if _is_flat_ui_spec(node):
        for element in node["elements"].values():
            if not isinstance(element, dict):
                continue
            node_type = element.get("type")
            if isinstance(node_type, str):
                component_types.add(node_type)
        return sorted(component_types)

    def walk(current: Any) -> None:
        if isinstance(current, dict):
            node_type = current.get("type")
            if isinstance(node_type, str) and any(key in current for key in ("props", "children")):
                component_types.add(node_type)
            for value in current.values():
                walk(value)
        elif isinstance(current, list):
            for item in current:
                walk(item)

    walk(node)
    return sorted(component_types)


def _collect_action_types(node: Any) -> set[str]:
    """递归收集 UI Spec 中出现的动作类型。

    功能：
        flat spec 把动作配置折叠进 `elements`，树形 Spec 则是直接嵌套在节点里。
        这里统一抽出运行时动作，保证 `ui_runtime.ui_actions` 和真实 Spec 保持一致。
    """
    action_types: set[str] = set()

    known_action_codes = _get_ui_catalog_service().get_all_action_codes()

    if _is_flat_ui_spec(node):
        for element in node["elements"].values():
            if isinstance(element, dict):
                _walk_action_payload(element, action_types, known_action_codes)
        return action_types

    _walk_action_payload(node, action_types, known_action_codes)
    return action_types


def _is_flat_ui_spec(node: Any) -> bool:
    """判断当前 UI Spec 是否已经是 `root/state/elements` 新协议。"""
    return isinstance(node, dict) and isinstance(node.get("root"), str) and isinstance(node.get("elements"), dict)


def _walk_action_payload(current: Any, action_types: set[str], known_action_codes: set[str]) -> None:
    """递归扫描动作定义载荷。

    功能：
        单独拆出这个 helper，是为了把“flat spec 扫 elements”和“旧树形 Spec 全量扫描”
        复用到同一套动作识别逻辑里，避免任务 1 之后两条分支再度分叉。
    """
    if isinstance(current, dict):
        action_type = current.get("type")
        action_name = current.get("action")
        if isinstance(action_type, str) and action_type in known_action_codes:
            action_types.add(action_type)
        if isinstance(action_name, str) and action_name in known_action_codes:
            action_types.add(action_name)
        for value in current.values():
            _walk_action_payload(value, action_types, known_action_codes)
    elif isinstance(current, list):
        for item in current:
            _walk_action_payload(item, action_types, known_action_codes)


def _infer_identifier_field(rows: list[dict[str, Any]]) -> str | None:
    """从结果集字段中推测可用于详情跳转的主键列。"""
    if not rows or not isinstance(rows[0], dict):
        return None

    keys = list(rows[0].keys())
    exact_matches = ("id", "code", "uuid")
    for exact in exact_matches:
        for key in keys:
            if key.lower() == exact:
                return key

    for key in keys:
        normalized = key.lower()
        if normalized.endswith("_id") or normalized.endswith("id"):
            return key
    return None


def _infer_page_size(params: dict[str, Any], row_count: int) -> int | None:
    """从查询参数中推断当前页大小。"""
    for key in ("pageSize", "page_size", "size", "limit"):
        value = params.get(key)
        if isinstance(value, int) and value > 0:
            return value
    return row_count or None


def _infer_current_page(params: dict[str, Any]) -> int | None:
    """从查询参数中推断当前页码。"""
    for key in ("page", "pageNum", "page_no", "pageIndex", "current"):
        value = params.get(key)
        if isinstance(value, int) and value > 0:
            return value
    return None


def _find_selected_entry(
    candidates: list[Any],
    routing_result: ApiQueryRoutingResult,
) -> ApiCatalogEntry | None:
    """根据路由结果从候选集中找出最终命中接口。"""
    return next(
        (candidate.entry for candidate in candidates if candidate.entry.id == routing_result.selected_api_id),
        None,
    )


def _build_plan_context_pool(execution_report: DagExecutionReport) -> dict[str, ApiQueryContextStepResult]:
    """将第三阶段执行报告转换成多步骤 `context_pool`。

    功能：
        `context_pool` 是第四、五阶段之间最关键的事实总线。这里必须保留每一步的
        状态、数据与运行时元信息，避免 Renderer 在多步骤场景下重新“猜”来源。
    """
    context_pool: dict[str, ApiQueryContextStepResult] = {}

    for step_id in execution_report.execution_order:
        record = execution_report.records_by_step_id[step_id]
        context_pool.update(
            _build_context_pool(
                record.entry,
                record.execution_result,
                step_id=record.step.step_id,
                extra_meta={
                    "plan_id": execution_report.plan.plan_id,
                    "depends_on": list(record.step.depends_on),
                    "resolved_params": record.resolved_params,
                },
            )
        )

    return context_pool


def _summarize_execution_report(execution_report: DagExecutionReport) -> ApiQueryExecutionStatus:
    """将多步骤执行结果收敛成对外主状态。

    功能：
        旧版 `api_query` 只有一个主步骤，现在需要在多步骤下给前端一个稳定总状态。
        这里优先表达“是否还有可展示的成功数据”，其次再表达是否发生部分失败。
    """
    statuses = [record.execution_result.status for record in execution_report.records_by_step_id.values()]

    if not statuses:
        return ApiQueryExecutionStatus.SKIPPED

    has_success = any(status == ApiQueryExecutionStatus.SUCCESS for status in statuses)
    has_error = any(status == ApiQueryExecutionStatus.ERROR for status in statuses)
    has_skipped = any(status == ApiQueryExecutionStatus.SKIPPED for status in statuses)

    if has_success and (has_error or has_skipped):
        return ApiQueryExecutionStatus.PARTIAL_SUCCESS
    if has_success:
        return ApiQueryExecutionStatus.SUCCESS
    if has_error:
        return ApiQueryExecutionStatus.ERROR
    if all(status == ApiQueryExecutionStatus.EMPTY for status in statuses):
        return ApiQueryExecutionStatus.EMPTY
    if any(status == ApiQueryExecutionStatus.EMPTY for status in statuses):
        return ApiQueryExecutionStatus.EMPTY
    return ApiQueryExecutionStatus.SKIPPED


def _select_response_anchor(execution_report: DagExecutionReport) -> DagStepExecutionRecord | None:
    """选择对外响应锚点步骤。

    功能：
        当前规则渲染器仍然更擅长消费“一个主结果”。这里优先选择最后一个成功步骤，
        若不存在，再回退到最后一个空结果或最后执行步骤，保证响应 envelope 有稳定锚点。
    """
    ordered_records = [execution_report.records_by_step_id[step_id] for step_id in execution_report.execution_order]

    for candidate_status in (
        ApiQueryExecutionStatus.SUCCESS,
        ApiQueryExecutionStatus.EMPTY,
        ApiQueryExecutionStatus.SKIPPED,
        ApiQueryExecutionStatus.ERROR,
    ):
        for record in reversed(ordered_records):
            if record.execution_result.status == candidate_status:
                return record

    return ordered_records[-1] if ordered_records else None


def _collect_execution_domains(execution_report: DagExecutionReport, fallback_domains: list[str]) -> list[str]:
    """汇总执行过程中实际涉及的业务域。"""
    executed_domains = []
    for step_id in execution_report.execution_order:
        domain = execution_report.records_by_step_id[step_id].entry.domain
        if domain and domain not in executed_domains:
            executed_domains.append(domain)

    if executed_domains:
        return executed_domains
    return list(fallback_domains)


def _normalize_rows(data: list[dict[str, Any]] | dict[str, Any] | None) -> list[dict[str, Any]]:
    """把单对象或空值统一折叠成列表形态。"""
    if data is None:
        return []
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    if isinstance(data, dict):
        return [data]
    return []


def _build_ui_data_from_execution_report(
    execution_report: DagExecutionReport,
    anchor_record: DagStepExecutionRecord | None,
) -> list[dict[str, Any]]:
    """为当前规则渲染器构造可展示的数据集。

    功能：
        多步骤 DAG 完成后，前端规则渲染器未必能直接理解整个 `context_pool`。
        这里做一个保守桥接：

        - 单步骤：继续展示原始业务数据
        - 多步骤：展示步骤摘要表，至少保证用户能看到每一步做了什么、结果如何
    """
    if len(execution_report.records_by_step_id) <= 1 and anchor_record is not None:
        return _normalize_data_for_ui(anchor_record.execution_result)

    summary_rows: list[dict[str, Any]] = []
    for step_id in execution_report.execution_order:
        record = execution_report.records_by_step_id[step_id]
        shaped_data, shaped_meta = _shape_context_data(record.execution_result.data)
        summary_rows.append(
            {
                "stepId": step_id,
                "domain": record.entry.domain,
                "apiPath": record.entry.path,
                "status": record.execution_result.status.value,
                "recordCount": _count_execution_rows(record.execution_result),
                "renderCount": shaped_meta["render_row_count"],
                "truncated": shaped_meta["truncated"],
            }
        )

    return summary_rows


def _normalize_data_for_ui(execution_result: ApiQueryExecutionResult) -> list[dict[str, Any]]:
    """将执行结果转换成适合 UI 渲染的行列表。"""
    data, _ = _shape_context_data(execution_result.data)
    return _normalize_rows(data)


def _count_execution_rows(execution_result: ApiQueryExecutionResult) -> int:
    """统计当前执行结果包含的记录数。"""
    if execution_result.data is None:
        return 0
    if isinstance(execution_result.data, list):
        return len(execution_result.data)
    return 1


def _count_ui_data_rows(
    ui_rows: list[dict[str, Any]],
    anchor_record: DagStepExecutionRecord | None,
    *,
    step_count: int,
) -> int:
    """统计响应层对外展示的数据条数。"""
    if (
        step_count == 1
        and anchor_record is not None
        and anchor_record.execution_result.status
        in {
            ApiQueryExecutionStatus.SUCCESS,
            ApiQueryExecutionStatus.EMPTY,
        }
    ):
        return _count_execution_rows(anchor_record.execution_result)
    return len(ui_rows)


def _build_runtime_from_execution_report(
    execution_report: DagExecutionReport,
    anchor_record: DagStepExecutionRecord | None,
    *,
    business_intents: list[ApiQueryBusinessIntent],
) -> ApiQueryUIRuntime:
    """根据执行报告推导前端运行时契约。

    功能：
        单步骤结果仍可复用列表/详情/表单契约；多步骤场景先收敛为保守的只读工作台，
        避免把错误的二跳动作挂到摘要表上。
    """
    if len(execution_report.records_by_step_id) == 1 and anchor_record is not None:
        return _build_ui_runtime(
            anchor_record.entry,
            anchor_record.execution_result,
            params=anchor_record.resolved_params,
            business_intents=business_intents,
        )

    return ApiQueryUIRuntime(
        components=_get_ui_catalog_service().get_component_codes(
            intent="query",
            requested_codes=["PlannerCard", "PlannerTable", "PlannerNotice"],
        ),
        ui_actions=_build_runtime_actions({"refresh", "export"}),
    )


def _infer_query_render_mode(
    execution_report: DagExecutionReport,
    anchor_record: DagStepExecutionRecord | None,
) -> str:
    """推断当前查询结果应使用的读态渲染模式。

    功能：
        规则 Renderer 需要区分“列表结果”、“单对象详情”和“多步骤摘要表”。
        这里把判定收敛在 route 层，是为了让渲染器消费一个明确语义，而不是继续从
        被裁剪后的 `data_for_ui` 反向猜测原始执行形态。

    Returns:
        `detail` / `table` / `summary_table` 三类之一。

    Edge Cases:
        - 多步骤结果即使最终只剩一行，也仍然视为 `summary_table`
        - 单步骤命中 `dict` 原始数据时，才升级为 `detail`
    """
    if len(execution_report.records_by_step_id) > 1:
        return "summary_table"
    if anchor_record is None:
        return "table"
    if isinstance(anchor_record.execution_result.data, dict):
        return "detail"
    return "table"


def _build_execution_title(
    execution_report: DagExecutionReport,
    anchor_record: DagStepExecutionRecord | None,
) -> str:
    """生成多步骤查询在 UI 顶部展示的标题。"""
    if len(execution_report.records_by_step_id) <= 1 and anchor_record is not None:
        return anchor_record.entry.description
    return f"执行计划 {execution_report.plan.plan_id}"


def _build_response_total(anchor_record: DagStepExecutionRecord | None) -> int:
    """提取当前响应锚点的总记录数。"""
    if anchor_record is None:
        return 0
    return anchor_record.execution_result.total


def _build_response_error(execution_report: DagExecutionReport) -> str | None:
    """提取多步骤执行的代表性错误信息。"""
    for step_id in execution_report.execution_order:
        record = execution_report.records_by_step_id[step_id]
        if record.execution_result.error:
            return record.execution_result.error
    return None


def _build_execution_skip_message(execution_report: DagExecutionReport) -> str:
    """把多步骤跳过原因收敛成适合前端展示的文案。"""
    for step_id in execution_report.execution_order:
        record = execution_report.records_by_step_id[step_id]
        execution_result = record.execution_result
        if execution_result.status == ApiQueryExecutionStatus.SKIPPED:
            return _build_skip_message(execution_result)
    return "由于缺少必要条件，当前查询未被执行。"


def _build_patch_mode_response(
    *,
    trace_id: str,
    execution_report: DagExecutionReport,
    aggregate_status: ApiQueryExecutionStatus,
    anchor_record: DagStepExecutionRecord | None,
    response_plan: ApiQueryExecutionPlan,
    runtime: ApiQueryUIRuntime,
    patch_context: ApiQueryPatchContext | None,
) -> ApiQueryResponse:
    """构造列表二跳的 patch 响应。

    功能：
        Patch 模式的核心目标是“只回当前页数据与最小状态增量”，而不是再让第五阶段生成
        一整页 `PlannerCard`。这里直接使用执行结果和运行时契约构造稳定的补丁载荷，
        从链路层面切断大 `pageSize` 时整页 Spec 被数据拖大的问题。

    Edge Cases:
        - `EMPTY` 仍返回 patch，只是把 `dataSource` 替换为空数组并同步分页总数
        - `ERROR / SKIPPED` 不再偷偷回退 full_spec，而是返回空操作 patch，让前端按错误态处理
    """
    requested_target = patch_context.mutation_target if patch_context is not None else None
    ui_runtime = runtime
    ui_spec = _build_list_patch_spec(
        anchor_record=anchor_record,
        runtime=ui_runtime,
        aggregate_status=aggregate_status,
        requested_target=requested_target,
    )
    return ApiQueryResponse(
        trace_id=trace_id,
        execution_status=aggregate_status,
        execution_plan=response_plan,
        ui_runtime=ui_runtime,
        ui_spec=ui_spec,
        error=_build_response_error(execution_report),
    )


def _build_list_patch_spec(
    *,
    anchor_record: DagStepExecutionRecord | None,
    runtime: ApiQueryUIRuntime,
    aggregate_status: ApiQueryExecutionStatus,
    requested_target: str | None,
) -> dict[str, Any]:
    """把单步列表结果压缩成前端可直接应用的 patch spec。

    功能：
        列表二跳请求的目标只是更新表格数据和分页状态，因此 patch spec 只保留：

        1. `dataSource`
        2. `pagination.currentPage`
        3. `pagination.pageSize`
        4. `pagination.total`

        这样前端无需整页重建，后端也不必在 patch 场景继续产出完整组件树。
    """
    mutation_target = runtime.list.pagination.mutation_target or requested_target or "report-table.props.dataSource"
    rows: list[dict[str, Any]] = []
    if (
        aggregate_status in {ApiQueryExecutionStatus.SUCCESS, ApiQueryExecutionStatus.EMPTY}
        and anchor_record is not None
    ):
        rows = _normalize_rows(anchor_record.execution_result.data)

    operations: list[dict[str, Any]] = []
    if aggregate_status in {ApiQueryExecutionStatus.SUCCESS, ApiQueryExecutionStatus.EMPTY}:
        operations.append(_build_patch_replace_operation(mutation_target, rows))
        pagination_container_path = _infer_patch_pagination_container_path(mutation_target)
        if pagination_container_path is not None:
            operations.extend(
                [
                    _build_patch_replace_operation(
                        f"{pagination_container_path}.currentPage",
                        runtime.list.pagination.current_page,
                    ),
                    _build_patch_replace_operation(
                        f"{pagination_container_path}.pageSize",
                        runtime.list.pagination.page_size,
                    ),
                    _build_patch_replace_operation(
                        f"{pagination_container_path}.total",
                        runtime.list.pagination.total,
                    ),
                ]
            )

    return {
        "kind": "patch",
        "patch_type": "list_query",
        "mutation_target": mutation_target,
        "operations": operations,
    }


def _build_patch_replace_operation(path: str, value: Any) -> dict[str, Any]:
    """构造单条 replace patch。

    功能：
        Patch 协议当前只暴露 replace，是为了把前端应用逻辑稳定在最小闭包里，避免这轮
        实现就引入 add/remove/move 等尚未验证的补丁语义。
    """
    return {
        "op": "replace",
        "path": path,
        "value": value,
    }


def _infer_patch_pagination_container_path(mutation_target: str) -> str | None:
    """从 `dataSource` 目标路径反推分页状态容器路径。

    功能：
        当前契约里 `mutation_target` 固定指向表格 `dataSource`，而 patch 还需要顺带更新
        同一个表格上的分页状态。这里通过约定式路径推导出分页容器，避免前端再维护第二套
        “当前表格 pagination 在哪”的静态映射。
    """
    if not mutation_target:
        return None
    if mutation_target.endswith(".dataSource"):
        return mutation_target[: -len(".dataSource")] + ".pagination"
    return None


def _find_missing_required_params(
    entry: ApiCatalogEntry,
    params: dict[str, Any],
) -> list[str]:
    """找出当前请求缺失的必填参数。

    功能：
        在真正调用上游前先做一次“安全刹车”，避免因为 LLM 没抽到主键或筛选项，
        反而触发宽查询、全表扫描或无意义的 4xx/5xx。

    Args:
        entry: 当前命中的注册表接口定义，包含 JSON Schema 的 `required` 声明。
        params: 路由阶段提取并校验后的参数。

    Returns:
        缺失字段名列表；空列表表示可以安全执行。
    """
    missing: list[str] = []
    for field in entry.param_schema.required:
        value = params.get(field)
        if value in (None, "", [], {}):
            missing.append(field)
    return missing


def _build_skipped_execution_result(
    *,
    trace_id: str,
    missing_required_params: list[str],
) -> ApiQueryExecutionResult:
    """为缺参场景构造 `SKIPPED` 结果。

    功能：
        把“网关主动放弃执行”的原因显式保存在状态总线里，而不是让前端只收到模糊错误。
    """
    return ApiQueryExecutionResult(
        status=ApiQueryExecutionStatus.SKIPPED,
        data=[],
        total=0,
        error=f"缺少必要参数：{', '.join(missing_required_params)}",
        error_code="MISSING_REQUIRED_PARAMS",
        trace_id=trace_id,
        skipped_reason="missing_required_params",
        meta={"missing_required_params": missing_required_params},
    )


def _build_context_pool(
    entry: ApiCatalogEntry,
    execution_result: ApiQueryExecutionResult,
    *,
    step_id: str | None = None,
    extra_meta: dict[str, Any] | None = None,
) -> dict[str, ApiQueryContextStepResult]:
    """将单接口执行结果包装成 `context_pool` 结构。

    功能：
        这里既服务当前的单步骤直达路径，也服务第三阶段多步骤 DAG 汇总。
        因此步骤 ID 和附加元数据都允许由上层覆盖，避免未来再次改契约。

    Returns:
        以 `step_id` 为 key 的步骤结果字典。
    """
    data, shape_meta = _shape_context_data(execution_result.data)
    meta = dict(execution_result.meta)
    meta.update(shape_meta)
    if extra_meta:
        meta.update(extra_meta)
    return {
        step_id or _build_step_id(entry): ApiQueryContextStepResult(
            status=execution_result.status,
            domain=entry.domain,
            api_id=entry.id,
            api_path=entry.path,
            method=entry.method,
            data=data,
            total=execution_result.total,
            error=_build_error_detail(execution_result),
            skipped_reason=execution_result.skipped_reason,
            meta=meta,
        )
    }


def _build_step_id(entry: ApiCatalogEntry) -> str:
    """生成稳定的步骤 ID，便于未来跨阶段引用和调试。"""
    return f"step_{entry.id}"


def _build_error_detail(
    execution_result: ApiQueryExecutionResult,
) -> ApiQueryExecutionErrorDetail | None:
    """把内部错误语义折叠成 Renderer 可消费的结构化错误对象。"""
    if not execution_result.error:
        return None
    return ApiQueryExecutionErrorDetail(
        code=execution_result.error_code,
        message=execution_result.error,
        retryable=execution_result.retryable,
    )


def _shape_context_data(
    data: list[dict[str, Any]] | dict[str, Any] | None,
) -> tuple[list[dict[str, Any]] | dict[str, Any], dict[str, Any]]:
    """裁剪进入 `context_pool` 和 Renderer 的数据体量。

    功能：
        把执行结果控制在一个稳定的上下文预算内，避免大列表在规则渲染或未来 LLM 渲染时
        直接拖垮链路，同时通过 `meta` 保留真实行数和截断信息。

    Returns:
        `(shaped_data, meta)`，其中 `meta` 明确说明是否发生截断。
    """
    if data is None:
        return [], {
            "raw_row_count": 0,
            "render_row_count": 0,
            "render_row_limit": _CONTEXT_ROW_LIMIT,
            "truncated": False,
        }

    if isinstance(data, dict):
        return data, {
            "raw_row_count": 1,
            "render_row_count": 1,
            "render_row_limit": _CONTEXT_ROW_LIMIT,
            "truncated": False,
        }

    rows = _normalize_rows(data)
    # 这里优先保留前几条样本，目的是服务查询结果预览，而不是在网关层承担完整翻页职责。
    limited_rows = rows[:_CONTEXT_ROW_LIMIT]
    truncated = len(rows) > len(limited_rows)
    meta = {
        "raw_row_count": len(rows),
        "render_row_count": len(limited_rows),
        "render_row_limit": _CONTEXT_ROW_LIMIT,
        "truncated": truncated,
    }
    if truncated:
        meta["truncated_count"] = len(rows) - len(limited_rows)
    return limited_rows, meta


def _build_skip_message(execution_result: ApiQueryExecutionResult) -> str:
    """将跳过原因翻译为适合前端提示的中文文案。"""
    if execution_result.skipped_reason == "skipped_due_to_empty_upstream":
        empty_bindings = execution_result.meta.get("empty_bindings", [])
        if empty_bindings:
            return "由于上游步骤未返回可继续传递的数据，当前依赖步骤已被安全跳过。"
        return "由于上游步骤没有返回可用数据，当前查询未继续执行。"
    if execution_result.skipped_reason == "missing_required_params":
        missing_fields = execution_result.meta.get("missing_required_params", [])
        if missing_fields:
            return f"由于缺少必要参数 {', '.join(missing_fields)}，当前查询未被执行。"
    if execution_result.error:
        return execution_result.error
    return "由于缺少必要条件，当前查询未被执行。"


def _maybe_attach_snapshot(
    snapshot_service: UISnapshotService,
    *,
    trace_id: str,
    business_intents: list[ApiQueryBusinessIntent],
    ui_spec: dict[str, Any] | None,
    ui_runtime: ApiQueryUIRuntime,
    metadata: dict[str, Any],
) -> ApiQueryUIRuntime:
    """在高危写意图场景下挂载快照凭证。"""
    if not snapshot_service.should_capture(business_intents):
        return ui_runtime

    snapshot = snapshot_service.create_snapshot(
        trace_id=trace_id,
        business_intents=business_intents,
        ui_spec=ui_spec,
        ui_runtime=ui_runtime,
        metadata=metadata,
    )
    return ui_runtime.model_copy(
        update={
            "audit": ui_runtime.audit.model_copy(
                update={
                    "enabled": True,
                    "snapshot_required": True,
                    "snapshot_id": snapshot.snapshot_id,
                    "risk_level": "high",
                }
            )
        }
    )


async def _generate_ui_spec_result(
    dynamic_ui: DynamicUIService,
    *,
    intent: str,
    data: Any,
    context: dict[str, Any] | None,
    status: ApiQueryExecutionStatus | str | None,
    runtime: ApiQueryUIRuntime | None,
    trace_id: str,
) -> UISpecBuildResult:
    """兼容第五阶段新旧接口，统一返回带 Guard 状态的结果对象。

    功能：
        当前主链已经升级为“Spec + 校验结果”模型，但部分测试替身仍只实现旧
        `generate_ui_spec`。这里提供一层兼容封装，保证路由逻辑先稳定切到新契约，
        再逐步收敛测试和其他调用方。
    """
    if hasattr(dynamic_ui, "generate_ui_spec_result"):
        try:
            return await dynamic_ui.generate_ui_spec_result(
                intent=intent,
                data=data,
                context=context,
                status=status,
                runtime=runtime,
                trace_id=trace_id,
            )
        except TypeError:
            return await dynamic_ui.generate_ui_spec_result(
                intent=intent,
                data=data,
                context=context,
                status=status,
                runtime=runtime,
            )

    try:
        spec = await dynamic_ui.generate_ui_spec(
            intent=intent,
            data=data,
            context=context,
            status=status,
            runtime=runtime,
            trace_id=trace_id,
        )
    except TypeError:
        spec = await dynamic_ui.generate_ui_spec(
            intent=intent,
            data=data,
            context=context,
            status=status,
            runtime=runtime,
        )
    return UISpecBuildResult(spec=spec, validation=UISpecValidationResult(), frozen=False)


def _summarize_validation_errors(validation: UISpecValidationResult) -> str:
    """压缩第五阶段 Guard 错误，便于 route 日志快速定位。"""
    if not validation.errors:
        return "[]"
    items = [f"{error.code}@{error.path}" for error in validation.errors[:5]]
    if len(validation.errors) > 5:
        items.append(f"...(+{len(validation.errors) - 5})")
    return "[" + ", ".join(items) + "]"
