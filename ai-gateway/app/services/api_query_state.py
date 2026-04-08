from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TypedDict

from pydantic import BaseModel, Field

from app.models.schemas import (
    ApiQueryExecutionPlan,
    ApiQueryExecutionStatus,
    ApiQueryResponse,
    ApiQueryRoutingResult,
    ApiQueryUIRuntime,
)
from app.services.api_catalog.dag_executor import DagStepExecutionRecord
from app.services.api_catalog.schema import ApiCatalogEntry, ApiCatalogSearchFilters


class ApiQueryRouteHintSummary(BaseModel):
    """第二阶段路由摘要。

    功能：
        外层图后续只需要知道“路由选中了谁、命中了哪些域、为什么降级”，不需要把
        整个 `ApiQueryRoutingResult` 原样塞进 state。
    """

    selected_api_id: str | None = Field(None, description="候选内最终命中的接口 ID")
    query_domains: list[str] = Field(default_factory=list, description="路由命中的业务域")
    business_intent_codes: list[str] = Field(default_factory=list, description="路由识别出的业务意图编码")
    route_status: str = Field("ok", description="路由阶段整体状态")
    route_error_code: str | None = Field(None, description="路由失败时的结构化错误码")
    reasoning: str | None = Field(None, description="路由阶段的解释说明")


class ApiQueryState(TypedDict, total=False):
    """`/api-query` 外层 Control State。

    功能：
        这里只允许放图推进真正需要的轻量事实，后续 LangGraph 外层工作流会基于这份
        控制状态做节点流转，而不是依赖 route 内部的大量局部变量。
    """

    request_mode: str
    query_text: str
    trace_id: str
    interaction_id: str | None
    conversation_id: str | None
    route_hint_summary: ApiQueryRouteHintSummary | None
    candidate_ids: list[str]
    plan: ApiQueryExecutionPlan | None
    execution_status: ApiQueryExecutionStatus | None
    error_code: str | None
    degrade_reason: str | None
    ui_spec: dict[str, Any] | None
    ui_runtime: ApiQueryUIRuntime | None
    response: ApiQueryResponse | None


class ApiQueryExecutionState(TypedDict, total=False):
    """`/api-query` 内层执行状态边界。

    功能：
        这份状态描述的是“执行子图需要追踪什么”，与外层 Control State 分层，避免把
        执行噪声直接扩散到整个请求工作流。
    """

    plan: ApiQueryExecutionPlan
    trace_id: str
    records_by_step_id: dict[str, DagStepExecutionRecord]
    execution_order: list[str]
    errors: list[str]
    aggregate_status: ApiQueryExecutionStatus | None


@dataclass(slots=True)
class ApiQueryRuntimeContext:
    """`/api-query` 运行时上下文。

    功能：
        这里承接不适合进入 graph state 的重量级或敏感对象，例如 `user_token`、原始
        候选对象和步骤白名单映射。这样后续状态图快照里不会混入敏感信息。

    入参业务含义：
        - `user_context`：第二阶段参数提取使用的用户上下文
        - `user_token`：透传给业务系统的授权头
        - `retrieval_filters`：自然语言链路下的检索过滤条件，供响应快照复盘
        - `candidates`：原始候选对象，仅请求期内使用
        - `step_entries`：`step_id -> ApiCatalogEntry` 的执行白名单
        - `log_prefix`：当前请求统一日志前缀
    """

    user_context: dict[str, Any] = field(default_factory=dict)
    user_token: str | None = None
    retrieval_filters: ApiCatalogSearchFilters | None = None
    candidates: list[Any] = field(default_factory=list)
    step_entries: dict[str, ApiCatalogEntry] = field(default_factory=dict)
    log_prefix: str = ""


def summarize_route_hint(route_hint: ApiQueryRoutingResult) -> ApiQueryRouteHintSummary:
    """把第二阶段原始结果压缩成可安全进入控制状态的摘要。"""

    return ApiQueryRouteHintSummary(
        selected_api_id=route_hint.selected_api_id,
        query_domains=list(route_hint.query_domains),
        business_intent_codes=list(route_hint.business_intents),
        route_status=route_hint.route_status,
        route_error_code=route_hint.route_error_code,
        reasoning=route_hint.reasoning,
    )


def build_execution_state(
    *,
    plan: ApiQueryExecutionPlan,
    trace_id: str,
    records_by_step_id: dict[str, DagStepExecutionRecord],
    execution_order: list[str],
) -> ApiQueryExecutionState:
    """构造当前阶段的执行状态快照。"""

    return {
        "plan": plan,
        "trace_id": trace_id,
        "records_by_step_id": records_by_step_id,
        "execution_order": list(execution_order),
        "errors": [
            record.execution_result.error
            for step_id in execution_order
            if (record := records_by_step_id[step_id]).execution_result.error
        ],
        "aggregate_status": None,
    }
