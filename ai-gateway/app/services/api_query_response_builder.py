from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Literal

from app.core.config import settings
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
    ApiQueryResponse,
    ApiQueryUIAction,
    ApiQueryUIRuntime,
)
from app.services.api_catalog.dag_executor import DagExecutionReport, DagStepExecutionRecord
from app.services.api_catalog.registry_source import ApiCatalogRegistrySource
from app.services.api_catalog.schema import ApiCatalogEntry
from app.services.api_catalog.schema_utils import extract_schema_description, resolve_schema_at_data_path
from app.services.api_query_request_schema_gate import build_request_schema_gated_fields
from app.services.api_query_state import ApiQueryExecutionState, ApiQueryRuntimeContext, ApiQueryState
from app.services.api_query_state import ApiQueryDeletePreviewContext
from app.services.dynamic_ui_service import DynamicUIService, UISpecBuildResult
from app.services.ui_catalog_service import UICatalogService
from app.services.ui_snapshot_service import UISnapshotService
from app.services.ui_spec_guard import UISpecValidationResult
from app.utils.state_path_utils import read_state_value, write_state_value
from app.services.api_catalog.business_intents import (
    NOOP_BUSINESS_INTENT,
    get_business_intent_catalog_service,
    normalize_business_intent_codes,
    resolve_business_intent_risk_level,
)

logger = logging.getLogger(__name__)

_QUERY_PARAM_SOURCE_BY_METHOD = {"GET": "queryParams", "POST": "body"}
_LIST_FILTER_EXCLUDED_FIELDS = {"id", "page", "pageNum", "pageSize", "size", "limit"}
# mutation confirm 表单会直接暴露给最终用户，因此需要隐藏纯系统维护字段，
# 避免把“创建/更新/删除时间”这类只读审计信息误当成可确认输入。
_MUTATION_FORM_HIDDEN_FIELD_NAMES = {
    "createtime",
    "createdtime",
    "createdat",
    "gmtcreate",
    "updatetime",
    "updatedtime",
    "updatedat",
    "gmtmodified",
    "deletetime",
    "deletedtime",
    "deletedat",
}
_MUTATION_FORM_HIDDEN_FIELD_TITLES = {"创建时间", "更新时间", "删除时间"}
_CREATE_MUTATION_QUERY_KEYWORDS = ("新增", "新建", "创建", "添加", "录入", "创建一个", "新增一个", "添加一个")
_CREATE_MUTATION_ENTRY_KEYWORDS = ("create", "add", "insert", "新增", "新建", "创建", "添加")
_CREATE_MUTATION_NAME_PATTERNS = (
    re.compile(
        r"(?:新增|新建|创建|添加|录入)(?:一个|一名|一条|一个新的|新的)?(?P<name>.+?)(?:角色|账号|部门|岗位|员工|用户)\s*$"
    ),
    re.compile(
        r"(?:新增|新建|创建|添加|录入).*(?:角色|账号|部门|岗位|员工|用户)[：: ]+(?P<name>[^，。；;]+)\s*$"
    ),
)
_NAME_LIKE_FIELD_TITLE_KEYWORDS = ("名称", "名字", "姓名")
_DELETE_DISPLAY_FIELD_PRIORITY = (
    "roleName",
    "roleCode",
    "appCode",
    "status",
    "id",
)
# 这里固定保留 5 条是为了给 Renderer 足够上下文，又避免把大结果集整包塞进生成链路导致注意力失焦。
_CONTEXT_ROW_LIMIT = 5
_SELECT_CANDIDATE_ROW_LIMIT = 50
_DEFAULT_MULTI_STEP_RENDER_POLICY = "summary_table"
_SUPPORTED_MULTI_STEP_RENDER_POLICIES = {
    "terminal_result",
    "composite_result",
    "summary_table",
    "aggregate_result",
    "auto_result",
}
_RESPONSE_SCHEMA_FALLBACK_PATHS = ("result", "data", "payload", "list", "records")


@dataclass(frozen=True, slots=True)
class _QueryUISelection:
    """封装本次查询读态渲染主数据，确保数据与渲染模式同源。"""

    data_for_ui: list[dict[str, Any]]
    render_mode: str
    source: str
    runtime_anchor_record: DagStepExecutionRecord | None = None
    response_field_label_index: dict[str, str] | None = None


class ApiQueryResponseBuilder:
    """`/api-query` 最终响应与降级收口器。

    功能：
        把 route 内分散的成功响应、patch/full_spec 分支、stage2/3 降级以及冻结态收口
        聚合成独立 seam。后续外层 LangGraph 只需要把状态推进到“已拿到执行结果”或
        “已确定降级原因”，最终都由这里统一折叠成 `ApiQueryResponse`。
    """

    def __init__(
        self,
        *,
        dynamic_ui: DynamicUIService,
        snapshot_service: UISnapshotService,
        ui_catalog_service: UICatalogService,
        registry_source: ApiCatalogRegistrySource,
    ) -> None:
        self._dynamic_ui = dynamic_ui
        self._snapshot_service = snapshot_service
        self._ui_catalog_service = ui_catalog_service
        self._registry_source = registry_source

    async def build_execution_response(
        self,
        *,
        state: ApiQueryState,
        runtime_context: ApiQueryRuntimeContext,
        execution_state: ApiQueryExecutionState,
        query_domains_hint: list[str],
        business_intent_codes: list[str],
    ) -> ApiQueryResponse:
        """把执行状态折叠为最终成功/部分成功响应。

        功能：
            当前路由阶段仍负责拿到执行报告，但“如何把执行事实压成前端契约”已经不应继续
            留在 HTTP 入口里。这一层会统一：

            1. 汇总主执行状态
            2. 选择响应锚点
            3. 生成或冻结 UI Spec
            4. 在必要时附加快照审计元数据

        Edge Cases:
            - 多步骤执行即使没有 anchor，也必须返回可解释的聚合状态和错误摘要
            - 高风险写意图只有在页面未冻结时才附加快照，避免给无效视图生成审计垃圾
        """

        execution_report = DagExecutionReport(
            plan=execution_state["plan"],
            records_by_step_id=execution_state["records_by_step_id"],
            execution_order=execution_state["execution_order"],
        )
        context_pool = _build_plan_context_pool(execution_report)
        wait_select_context_pool = _build_wait_select_context_pool(execution_report)
        if wait_select_context_pool:
            context_pool.update(wait_select_context_pool)
        aggregate_status = _summarize_execution_report(execution_report)
        execution_state["aggregate_status"] = aggregate_status
        state["execution_status"] = aggregate_status

        anchor_record = _select_response_anchor(execution_report)
        internal_query_domains = _collect_execution_domains(execution_report, query_domains_hint)
        query_domains = _format_query_domains_for_response(internal_query_domains)
        business_intents = _build_business_intents(business_intent_codes)
        response_plan = _build_response_execution_plan(execution_report.plan, runtime_context.step_entries)
        state["plan"] = response_plan
        created_by = _normalize_response_created_by(runtime_context.user_context)

        # 运行时契约与 UI 主数据必须从同一份执行报告派生，避免前端看到的元数据与表格内容错位。
        multi_step_render_policy = _resolve_multi_step_render_policy(settings.api_query_multi_step_render_policy)
        ui_selection = _select_query_ui_payload(
            execution_report,
            anchor_record,
            multi_step_render_policy=multi_step_render_policy,
        )
        response_field_label_index = (
            ui_selection.response_field_label_index
            or _build_response_field_label_index(ui_selection.runtime_anchor_record)
        )
        data_for_ui = ui_selection.data_for_ui
        runtime = _build_runtime_from_execution_report(
            execution_report,
            anchor_record,
            business_intents=business_intents,
            ui_catalog_service=self._ui_catalog_service,
            runtime_anchor_record=ui_selection.runtime_anchor_record,
        )
        runtime = await _enrich_detail_runtime_request_schema(
            runtime,
            registry_source=self._registry_source,
        )

        ui_build_result = await _generate_ui_spec_result(
            self._dynamic_ui,
            intent="query",
            data=data_for_ui,
            context={
                "question": state["query_text"],
                "user_query": state["query_text"],
                "title": _build_execution_title(execution_report, anchor_record),
                "detail_title": anchor_record.entry.description if anchor_record else "详情信息",
                "total": _build_response_total(anchor_record),
                "api_id": anchor_record.entry.id if anchor_record else None,
                "error": _build_response_error(execution_report),
                "empty_message": "未查到符合条件的数据，请调整筛选条件后重试。",
                "skip_message": _build_execution_skip_message(execution_report),
                "partial_message": "部分步骤执行失败或被短路，当前仅展示可安全返回的数据。",
                "query_render_mode": ui_selection.render_mode,
                "flow_num": state["trace_id"],
                "created_by": created_by,
                "request_params": dict(anchor_record.resolved_params) if anchor_record is not None else {},
                "context_pool": {step_id: step.model_dump(exclude_none=True) for step_id, step in context_pool.items()},
                "row_actions": _build_wait_select_row_actions(execution_report),
                "business_intents": [intent.model_dump() for intent in business_intents],
                # 把 response_schema 的 description/title 预先解析成字段显示名索引；
                # Renderer 仅消费该只读映射做展示，不会污染实际请求参数键名。
                "response_field_label_index": response_field_label_index,
            },
            status=aggregate_status,
            runtime=runtime,
            trace_id=state["trace_id"],
        )
        ui_spec = ui_build_result.spec
        runtime = await _enrich_runtime_from_ui_spec(
            runtime,
            ui_spec,
            business_intents=business_intents,
            trace_id=state["trace_id"],
            registry_source=self._registry_source,
        )
        ui_runtime = _finalize_render_runtime(
            runtime,
            ui_spec,
            ui_build_result,
            ui_catalog_service=self._ui_catalog_service,
        )

        if ui_build_result.frozen:
            logger.warning(
                "%s stage5 ui frozen errors=%s",
                runtime_context.log_prefix,
                _summarize_validation_errors(ui_build_result.validation),
            )
        else:
            snapshot_metadata = {
                "request_mode": state["request_mode"],
                "plan_id": execution_report.plan.plan_id,
                "step_ids": [step.step_id for step in execution_report.plan.steps],
                "api_id": anchor_record.entry.id if anchor_record else None,
                "api_path": anchor_record.entry.path if anchor_record else None,
                "query_domains": query_domains,
            }
            if runtime_context.retrieval_filters is not None:
                # 只有自然语言模式真的经过了召回链路，才保留检索过滤条件供排障复盘。
                snapshot_metadata["retrieval_filters"] = runtime_context.retrieval_filters.model_dump()

            ui_runtime = _maybe_attach_snapshot(
                self._snapshot_service,
                trace_id=state["trace_id"],
                business_intents=business_intents,
                ui_spec=ui_spec,
                ui_runtime=ui_runtime,
                metadata=snapshot_metadata,
            )

        logger.info(
            "%s success mode=%s status=%s api_id=%s step_count=%s render_policy=%s render_mode=%s payload_source=%s",
            runtime_context.log_prefix,
            state["request_mode"],
            aggregate_status,
            anchor_record.entry.id if anchor_record else None,
            len(execution_report.records_by_step_id),
            multi_step_render_policy,
            ui_selection.render_mode,
            ui_selection.source,
        )
        response = ApiQueryResponse(
            trace_id=state["trace_id"],
            execution_status=aggregate_status,
            execution_plan=response_plan,
            ui_runtime=ui_runtime,
            ui_spec=ui_spec,
            error=_build_response_error(execution_report),
        )
        state["ui_runtime"] = ui_runtime
        state["ui_spec"] = ui_spec
        state["response"] = response
        return response

    async def build_stage2_degrade_response(
        self,
        *,
        state: ApiQueryState,
        title: str,
        message: str,
        error_code: str,
        query_domains: list[str],
        business_intent_codes: list[str],
        reasoning: str | None = None,
    ) -> ApiQueryResponse:
        """把第二阶段失败折叠为冻结只读 Notice。

        Edge Cases:
            - stage2 降级也会保留 query_domains 与 reasoning 摘要，方便解释为什么没继续执行
            - 这里固定返回只读 Notice，防止前端把“未识别路由”误渲染成空列表
        """

        response_query_domains = _format_query_domains_for_response(query_domains)
        execution_result = ApiQueryExecutionResult(
            status=ApiQueryExecutionStatus.SKIPPED,
            data=[],
            total=0,
            error=message,
            error_code=error_code,
            retryable=True,
            trace_id=state["trace_id"],
            skipped_reason=error_code,
            meta={"stage": "stage2", "query": state["query_text"], "reasoning": reasoning},
        )
        business_intents = _build_business_intents(business_intent_codes)
        context_pool = {
            "stage2_routing": ApiQueryContextStepResult(
                status=ApiQueryExecutionStatus.SKIPPED,
                domain=response_query_domains[0] if len(response_query_domains) == 1 else None,
                data=[],
                total=0,
                error=ApiQueryExecutionErrorDetail(code=error_code, message=message, retryable=True),
                skipped_reason=error_code,
                meta={"stage": "stage2", "query_domains": response_query_domains, "reasoning": reasoning},
            )
        }
        base_runtime = ApiQueryUIRuntime(
            components=["PlannerCard", "PlannerNotice"],
            ui_actions=_build_runtime_actions({"refresh"}, ui_catalog_service=self._ui_catalog_service),
        )
        ui_build_result = await _generate_ui_spec_result(
            self._dynamic_ui,
            intent="query",
            data=[],
            context={
                "title": title,
                "user_query": state["query_text"],
                "skip_message": message,
                "error": message,
                "context_pool": {step_id: step.model_dump(exclude_none=True) for step_id, step in context_pool.items()},
                "business_intents": [intent.model_dump() for intent in business_intents],
            },
            status=execution_result.status,
            runtime=base_runtime,
            trace_id=state["trace_id"],
        )
        ui_runtime = _finalize_render_runtime(
            base_runtime,
            ui_build_result.spec,
            ui_build_result,
            ui_catalog_service=self._ui_catalog_service,
        )
        response = ApiQueryResponse(
            trace_id=state["trace_id"],
            execution_status=execution_result.status,
            ui_runtime=ui_runtime,
            ui_spec=ui_build_result.spec,
            error=message,
        )
        state["execution_status"] = execution_result.status
        state["error_code"] = error_code
        state["degrade_reason"] = message
        state["ui_runtime"] = ui_runtime
        state["ui_spec"] = ui_build_result.spec
        state["response"] = response
        return response

    async def build_stage3_degrade_response(
        self,
        *,
        state: ApiQueryState,
        title: str,
        message: str,
        error_code: str,
        query_domains: list[str],
        business_intent_codes: list[str],
        reasoning: str | None = None,
    ) -> ApiQueryResponse:
        """把第三阶段规划失败折叠为冻结只读 Notice。

        Edge Cases:
            - stage3 降级强调的是“计划不可安全执行”，因此不会继续保留任何可交互查询动作
            - 虽然是降级页面，仍会把 stage3 原因写入 context_pool，方便渲染器生成解释文案
        """

        response_query_domains = _format_query_domains_for_response(query_domains)
        execution_result = ApiQueryExecutionResult(
            status=ApiQueryExecutionStatus.SKIPPED,
            data=[],
            total=0,
            error=message,
            error_code=error_code,
            retryable=True,
            trace_id=state["trace_id"],
            skipped_reason=error_code,
            meta={"stage": "stage3", "query": state["query_text"], "reasoning": reasoning},
        )
        business_intents = _build_business_intents(business_intent_codes)
        context_pool = {
            "stage3_planner": ApiQueryContextStepResult(
                status=ApiQueryExecutionStatus.SKIPPED,
                domain=response_query_domains[0] if len(response_query_domains) == 1 else None,
                data=[],
                total=0,
                error=ApiQueryExecutionErrorDetail(code=error_code, message=message, retryable=True),
                skipped_reason=error_code,
                meta={"stage": "stage3", "query_domains": response_query_domains, "reasoning": reasoning},
            )
        }
        base_runtime = ApiQueryUIRuntime(
            components=["PlannerCard", "PlannerNotice"],
            ui_actions=_build_runtime_actions({"refresh"}, ui_catalog_service=self._ui_catalog_service),
        )
        ui_build_result = await _generate_ui_spec_result(
            self._dynamic_ui,
            intent="query",
            data=[],
            context={
                "title": title,
                "user_query": state["query_text"],
                "skip_message": message,
                "error": message,
                "context_pool": {step_id: step.model_dump(exclude_none=True) for step_id, step in context_pool.items()},
                "business_intents": [intent.model_dump() for intent in business_intents],
            },
            status=execution_result.status,
            runtime=base_runtime,
            trace_id=state["trace_id"],
        )
        ui_runtime = _finalize_render_runtime(
            base_runtime,
            ui_build_result.spec,
            ui_build_result,
            ui_catalog_service=self._ui_catalog_service,
        )
        response = ApiQueryResponse(
            trace_id=state["trace_id"],
            execution_status=execution_result.status,
            ui_runtime=ui_runtime,
            ui_spec=ui_build_result.spec,
            error=message,
        )
        state["execution_status"] = execution_result.status
        state["error_code"] = error_code
        state["degrade_reason"] = message
        state["ui_runtime"] = ui_runtime
        state["ui_spec"] = ui_build_result.spec
        state["response"] = response
        return response

    async def build_mutation_form_response(
        self,
        *,
        state: ApiQueryState,
        entry: Any,
        pre_fill_params: dict[str, Any],
        business_intent_code: str,
        query_domains_hint: list[str],
        created_by: str | None = None,
    ) -> ApiQueryResponse:
        """把 mutation 表单快路折叠为预填表单 UI。

        功能：
            当 `_build_plan` 识别到单候选 mutation 接口时，由此方法构造：

            1. `execution_status=SKIPPED`（"AI 读，人工确认写"安全契约）
            2. `ui_runtime.form.enabled=true`，包含表单字段的提交契约
            3. `ui_spec`：由 DynamicUIService 生成带 PlannerForm + PlannerInput 的表单 Spec
            4. `execution_plan`：包含 mutation 接口的步骤，供前端确认后直接调用业务系统

        AI 读人工确认：
            前端拿到响应后，展示预填表单让用户核对。用户点击"确认"后，直接调用
            `ui_runtime.form.route_url` 指向的 runtime invoke 入口提交变更；`/api-query`
            只负责生成待确认表单，不参与最终写入。

        Edge Cases:
            - mutation 响应对外固定表现为 `SKIPPED`，明确表达“未真正执行写操作”
            - 创建类 mutation 会在预填阶段补名称兜底，避免确认页出现空标题字段
            - execution_plan 仍会保留 mutation 步骤，供前端确认后发起二跳调用
        """

        business_intents = _build_business_intents([business_intent_code])
        normalized_pre_fill_params = _enrich_mutation_prefill_params(
            entry=entry,
            pre_fill_params=pre_fill_params,
            query_text=state.get("query_text", ""),
        )

        # 表单字段必须严格基于 request_schema 生成，避免 UI 展示字段和最终提交契约脱节。
        form_fields = _build_mutation_form_fields(
            entry,
            normalized_pre_fill_params,
            query_text=state.get("query_text", ""),
        )

        # 构造带 form 的运行时契约
        form_code = f"{entry.id}_form"
        requested_component_codes = [
            "PlannerCard",
            "PlannerMetric",
            "PlannerInfoGrid",
            "PlannerForm",
            "PlannerInput",
            "PlannerSelect",
            "PlannerButton",
            "PlannerNotice",
        ]
        components = self._ui_catalog_service.get_component_codes(intent="query", requested_codes=requested_component_codes)
        action_codes = {"remoteMutation", "refresh"}
        base_runtime = ApiQueryUIRuntime(
            components=components,
            ui_actions=_build_runtime_actions(action_codes, ui_catalog_service=self._ui_catalog_service),
            form=ApiQueryFormRuntime(
                enabled=True,
                form_code=form_code,
                mode=_infer_form_mode(form_fields),
                api_id=entry.id,
                # 前端确认提交时必须命中 runtime invoke 入口，才能复用 business-server
                # 对 ui_endpoints 的真实装配能力；这里不能返回业务 path，否则前端会拿
                # 不到 flowNum/queryParams/body 这层运行时壳。
                route_url=_build_runtime_invoke_url(entry.id),
                ui_action="remoteMutation",
                request_schema_fields=list(entry.param_schema.properties),
                state_path="/form",
                fields=form_fields,
                submit=ApiQueryFormSubmitRuntime(
                    business_intent=business_intent_code,
                    confirm_required=True,
                ),
            ),
        )

        # 生成预填表单 UI Spec 时同步注入 flow_num/created_by，保证前端确认后无需再拼装身份壳。
        form_state = _build_prefilled_form_state(
            fields=form_fields,
            pre_fill_params=normalized_pre_fill_params,
        )
        ui_build_result = await _generate_ui_spec_result(
            self._dynamic_ui,
            intent="mutation_form",
            data=normalized_pre_fill_params,
            context={
                "title": f"确认修改：{entry.description}",
                "user_query": state.get("query_text", ""),
                "api_id": entry.id,
                "form_code": form_code,
                "business_intent": business_intent_code,
                "pre_fill_params": normalized_pre_fill_params,
                "form_fields": [f.model_dump(exclude_none=True) for f in form_fields],
                "form_state": form_state,
                "flow_num": state["trace_id"],
                "created_by": created_by or "",
                "business_intents": [intent.model_dump() for intent in business_intents],
            },
            status=ApiQueryExecutionStatus.SKIPPED,
            runtime=base_runtime,
            trace_id=state["trace_id"],
        )
        ui_runtime = _finalize_render_runtime(
            base_runtime,
            ui_build_result.spec,
            ui_build_result,
            ui_catalog_service=self._ui_catalog_service,
        )

        # execution_plan 使用 mutation 接口的步骤，供前端确认后调用
        from app.models.schemas import ApiQueryExecutionPlan, ApiQueryPlanStep

        mutation_plan = ApiQueryExecutionPlan(
            plan_id=f"mutation_{state['trace_id'][:8]}",
            steps=[
                ApiQueryPlanStep(
                    step_id=f"step_{entry.id}",
                    api_id=entry.id,
                    api_path=entry.path,
                    params=normalized_pre_fill_params,
                    depends_on=[],
                )
            ],
        )

        logger.info(
            "api_query[trace=%s] mutation_form response built api_id=%s fields=%s",
            state["trace_id"],
            entry.id,
            [f.name for f in form_fields],
        )
        response = ApiQueryResponse(
            trace_id=state["trace_id"],
            execution_status=ApiQueryExecutionStatus.SKIPPED,
            execution_plan=mutation_plan,
            ui_runtime=ui_runtime,
            ui_spec=ui_build_result.spec,
            error=None,
        )
        state["execution_status"] = ApiQueryExecutionStatus.SKIPPED
        state["ui_runtime"] = ui_runtime
        state["ui_spec"] = ui_build_result.spec
        state["plan"] = mutation_plan
        state["response"] = response
        return response

    async def build_delete_preview_response(
        self,
        *,
        state: ApiQueryState,
        delete_preview_context: ApiQueryDeletePreviewContext,
        created_by: str | None = None,
    ) -> ApiQueryResponse:
        """把删除预检结果折叠成 notice / 确认表单 / 候选列表。

        功能：
            删除类 mutation 不能直接下发表单。这里根据 workflow 预检出的 0/1/N 候选：

            1. `missing` / `unresolved`：只读提示
            2. `confirm`：带确认删除按钮的只读表单
            3. `candidates`：候选列表，每行直接挂删除动作

        Edge Cases:
            - 删除预检状态决定最终 UI 形态，响应层不再重新猜测候选数量
            - 所有删除预检结果都保持 `SKIPPED`，明确表明尚未实际删除数据
        """

        if delete_preview_context.status in {"missing", "unresolved"}:
            return await self._build_delete_notice_response(
                state=state,
                delete_preview_context=delete_preview_context,
            )
        if delete_preview_context.status == "confirm":
            return await self._build_delete_confirm_response(
                state=state,
                delete_preview_context=delete_preview_context,
                created_by=created_by,
            )
        return await self._build_delete_candidates_response(
            state=state,
            delete_preview_context=delete_preview_context,
            created_by=created_by,
        )

    async def _build_delete_notice_response(
        self,
        *,
        state: ApiQueryState,
        delete_preview_context: ApiQueryDeletePreviewContext,
    ) -> ApiQueryResponse:
        """为删除预检的未命中或无法确认场景构造只读提示。

        Edge Cases:
            - `missing` 不视为系统错误，因此对外 `error` 为空；`unresolved` 才透出错误文案
            - 删除无法确认时只保留刷新动作，防止前端继续误触发写链
        """

        message = delete_preview_context.message or "当前无法确认待删除角色，请稍后重试。"
        title = "未找到待删除角色" if delete_preview_context.status == "missing" else "无法确认删除对象"
        base_runtime = ApiQueryUIRuntime(
            components=["PlannerCard", "PlannerNotice"],
            ui_actions=_build_runtime_actions({"refresh"}, ui_catalog_service=self._ui_catalog_service),
        )
        ui_build_result = await _generate_ui_spec_result(
            self._dynamic_ui,
            intent="query",
            data=[],
            context={
                "title": title,
                "user_query": state.get("query_text", ""),
                "skip_message": message,
                "error": message,
            },
            status=ApiQueryExecutionStatus.SKIPPED,
            runtime=base_runtime,
            trace_id=state["trace_id"],
        )
        ui_runtime = _finalize_render_runtime(
            base_runtime,
            ui_build_result.spec,
            ui_build_result,
            ui_catalog_service=self._ui_catalog_service,
        )
        response = ApiQueryResponse(
            trace_id=state["trace_id"],
            execution_status=ApiQueryExecutionStatus.SKIPPED,
            execution_plan=None,
            ui_runtime=ui_runtime,
            ui_spec=ui_build_result.spec,
            error=message if delete_preview_context.status == "unresolved" else None,
        )
        state["execution_status"] = ApiQueryExecutionStatus.SKIPPED
        state["ui_runtime"] = ui_runtime
        state["ui_spec"] = ui_build_result.spec
        state["plan"] = None
        state["response"] = response
        return response

    async def _build_delete_confirm_response(
        self,
        *,
        state: ApiQueryState,
        delete_preview_context: ApiQueryDeletePreviewContext,
        created_by: str | None = None,
    ) -> ApiQueryResponse:
        """单候选删除预检：输出确认删除表单。

        Edge Cases:
            - 删除确认页字段全部只读，避免把“确认删除”变成“现场编辑后再删”
            - submit_payload 优先尊重预检阶段已解析出的结果，确保真正删除目标与候选一致
        """

        row = delete_preview_context.matched_rows[0]
        form_fields = _build_delete_confirm_form_fields(
            row=row,
            identifier_field=delete_preview_context.identifier_field,
            lookup_entry=delete_preview_context.lookup_entry,
        )
        submit_payload = delete_preview_context.submit_payload or _build_delete_submit_payload(
            delete_entry=delete_preview_context.delete_entry,
            row=row,
            identifier_field=delete_preview_context.identifier_field,
        )
        form_state = {
            "form": {
                field.submit_key: row.get(field.submit_key)
                for field in form_fields
            }
        }

        form_code = f"{delete_preview_context.delete_entry.id}_confirm"
        base_runtime = ApiQueryUIRuntime(
            components=["PlannerButton", "PlannerCard", "PlannerForm", "PlannerMetric"],
            ui_actions=_build_runtime_actions({"remoteMutation", "refresh"}, ui_catalog_service=self._ui_catalog_service),
            form=ApiQueryFormRuntime(
                enabled=True,
                form_code=form_code,
                mode="confirm",
                api_id=delete_preview_context.delete_entry.id,
                route_url=_build_runtime_invoke_url(delete_preview_context.delete_entry.id),
                ui_action="remoteMutation",
                request_schema_fields=list(delete_preview_context.delete_entry.param_schema.properties),
                state_path="/form",
                fields=form_fields,
                submit=ApiQueryFormSubmitRuntime(
                    business_intent=delete_preview_context.business_intent_code,
                    confirm_required=True,
                ),
            ),
        )
        entity_name = delete_preview_context.target_name or row.get("roleName") or row.get("name") or "目标角色"
        # 删除确认页本质上仍是 mutation_form，只是通过只读字段和危险文案收紧交互范围。
        ui_build_result = await _generate_ui_spec_result(
            self._dynamic_ui,
            intent="mutation_form",
            data=row,
            context={
                "title": f"确认删除：{entity_name}",
                "subtitle": "请确认后执行删除操作，删除后不可恢复",
                "submit_label": "确认删除",
                "submit_payload": submit_payload,
                "form_fields": [field.model_dump(exclude_none=True) for field in form_fields],
                "form_state": form_state,
                "flow_num": state["trace_id"],
                "created_by": created_by or "",
            },
            status=ApiQueryExecutionStatus.SKIPPED,
            runtime=base_runtime,
            trace_id=state["trace_id"],
        )
        ui_runtime = _finalize_render_runtime(
            base_runtime,
            ui_build_result.spec,
            ui_build_result,
            ui_catalog_service=self._ui_catalog_service,
        )
        execution_plan = ApiQueryExecutionPlan(
            plan_id=f"mutation_{state['trace_id'][:8]}",
            steps=[
                {
                    "step_id": f"step_{delete_preview_context.delete_entry.id}",
                    "api_id": delete_preview_context.delete_entry.id,
                    "api_path": delete_preview_context.delete_entry.path,
                    "params": submit_payload,
                    "depends_on": [],
                }
            ],
        )
        response = ApiQueryResponse(
            trace_id=state["trace_id"],
            execution_status=ApiQueryExecutionStatus.SKIPPED,
            execution_plan=execution_plan,
            ui_runtime=ui_runtime,
            ui_spec=ui_build_result.spec,
            error=None,
        )
        state["execution_status"] = ApiQueryExecutionStatus.SKIPPED
        state["ui_runtime"] = ui_runtime
        state["ui_spec"] = ui_build_result.spec
        state["plan"] = execution_plan
        state["response"] = response
        return response

    async def _build_delete_candidates_response(
        self,
        *,
        state: ApiQueryState,
        delete_preview_context: ApiQueryDeletePreviewContext,
        created_by: str | None = None,
    ) -> ApiQueryResponse:
        """多候选删除预检：输出候选列表，并为每行挂删除动作。

        Edge Cases:
            - 页面展示候选列表时，渲染阶段临时按 `SUCCESS` 处理，否则规则渲染会被 `SKIPPED` Notice 短路
            - 每行动作模板只绑定标识字段，不把整行数据整包塞进删除请求体，避免误删字段漂移
        """

        candidate_rows = _build_delete_candidate_rows(
            rows=delete_preview_context.matched_rows,
            identifier_field=delete_preview_context.identifier_field,
        )
        row_actions = [
            {
                "type": "remoteMutation",
                "label": "删除该角色",
                "params": {
                    "api_id": delete_preview_context.delete_entry.id,
                    **build_request_schema_gated_fields(
                        api_id=delete_preview_context.delete_entry.id,
                        param_source="body",
                        params=_build_delete_row_payload_template(
                            delete_entry=delete_preview_context.delete_entry,
                            identifier_field=delete_preview_context.identifier_field,
                        ),
                        flow_num=state["trace_id"],
                        created_by=created_by or "",
                        allowed_fields=delete_preview_context.delete_entry.param_schema.properties.keys(),
                    ),
                    "source": {
                        "identifier_field": delete_preview_context.identifier_field,
                        "value_type": _normalize_runtime_value_type(
                            None,
                            fallback_value=candidate_rows[0].get(delete_preview_context.identifier_field),
                        ),
                        "required": True,
                    },
                },
            }
        ]
        base_runtime = ApiQueryUIRuntime(
            components=["PlannerCard", "PlannerTable", "PlannerForm", "PlannerPagination", "PlannerButton"],
            ui_actions=_build_runtime_actions({"remoteMutation", "refresh"}, ui_catalog_service=self._ui_catalog_service),
        )
        ui_build_result = await _generate_ui_spec_result(
            self._dynamic_ui,
            intent="query",
            data=candidate_rows,
            context={
                "question": "删除角色候选",
                "user_query": state.get("query_text", ""),
                "total": len(candidate_rows),
                "flow_num": state["trace_id"],
                "created_by": created_by or "",
                "row_actions": row_actions,
            },
            # 此处展示的是查询出的候选表，而不是“跳过提示”；若继续传 SKIPPED，
            # 规则渲染会被通用 Notice 分支短路，因此只在页面生成阶段临时视作成功。
            status=ApiQueryExecutionStatus.SUCCESS,
            runtime=base_runtime,
            trace_id=state["trace_id"],
        )
        ui_runtime = _finalize_render_runtime(
            base_runtime,
            ui_build_result.spec,
            ui_build_result,
            ui_catalog_service=self._ui_catalog_service,
        )
        response = ApiQueryResponse(
            trace_id=state["trace_id"],
            execution_status=ApiQueryExecutionStatus.SKIPPED,
            execution_plan=None,
            ui_runtime=ui_runtime,
            ui_spec=ui_build_result.spec,
            error=None,
        )
        state["execution_status"] = ApiQueryExecutionStatus.SKIPPED
        state["ui_runtime"] = ui_runtime
        state["ui_spec"] = ui_build_result.spec
        state["plan"] = None
        state["response"] = response
        return response




def _build_business_intents(intent_codes: list[str]) -> list[ApiQueryBusinessIntent]:
    """将业务意图编码转换为对外响应对象。

    功能：
        对外响应不应暴露内部目录的全部意图定义，因此这里只输出允许公开、且当前请求真正命中的
        意图列表；若没有合法命中，则回退到 `none`。

    Edge Cases:
        - 被禁用或禁止出现在响应中的意图会被直接过滤
        - 空结果会回退到 noop 意图，避免前端再写一套“无意图”兼容逻辑
    """

    intent_catalog = get_business_intent_catalog_service()
    codes = normalize_business_intent_codes(intent_codes)
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


def _build_mutation_form_fields(
    entry: Any,
    pre_fill_params: dict[str, Any],
    *,
    query_text: str = "",
) -> list[ApiQueryFormFieldRuntime]:
    """从 mutation 接口的 param_schema 与预填值构造表单字段运行时契约。

    设计意图：
        mutation form 快路不走真实业务回查，因此 request_schema 是表单字段定义的唯一来源。
        现阶段策略是“按 request_schema 全量展示”，只隐藏创建/更新/删除时间这类系统维护
        字段，避免确认页和实际提交契约脱节。

        LLM 提取的预填值决定了该字段的初始 `state_path` 绑定和 `source_kind`
        （已填写 → context，未填写 → user_input）。

        主键/ID 字段（名称以 id/Id 结尾或以 Id 开头）会标记为 `writable=False`，
        让 `_infer_form_mode` 推导出 `edit`，符合"修改已知记录"的语义。

    Edge Cases:
        - 创建类 mutation 会隐藏纯 `id` 字段，避免把服务端生成主键误展示给用户填写
        - 字典字段会转为 `PlannerSelect` 语义，确保前端走稳定选项源而不是自由输入
    """

    schema_properties = entry.param_schema.properties if entry.param_schema else {}
    required_fields = set(entry.param_schema.required) if entry.param_schema else set()
    is_create_mutation = _is_create_mutation_form(query_text=query_text, entry=entry)

    all_visible_fields: list[ApiQueryFormFieldRuntime] = []

    for field_name, prop in schema_properties.items():
        if _should_hide_mutation_form_field(
            field_name=field_name,
            schema=prop,
            hide_identifier=is_create_mutation,
        ):
            continue

        has_value = field_name in pre_fill_params and pre_fill_params[field_name] not in ("", None)

        # 判断是否为标识符/主键字段：名称以 Id/id 结尾，或以 id/Id 开头（不区分大小写）
        lower_name = field_name.lower()
        is_identifier = lower_name.endswith("id") or lower_name.startswith("id")

        # 标识符字段不允许编辑（用于精确定位记录）
        writable = not is_identifier
        source_kind: Literal["context", "user_input", "dictionary", "derived"] = (
            "context" if (has_value or is_identifier) else "user_input"
        )

        # 推断值类型
        prop_type = prop.get("type", "string")
        value_type = _normalize_runtime_value_type(prop_type)

        # 推断选项来源
        option_source: ApiQueryFormOptionSourceRuntime | None = None
        if prop_type == "string" and prop.get("enum"):
            option_source = ApiQueryFormOptionSourceRuntime(type="enum")
        elif prop.get("dict_code"):
            option_source = ApiQueryFormOptionSourceRuntime(type="dict", dict_code=str(prop["dict_code"]))
            source_kind = "dictionary"

        field_runtime = ApiQueryFormFieldRuntime(
            name=prop.get("title") or field_name,
            value_type=value_type,
            state_path=f"/form/{field_name}",
            submit_key=field_name,
            required=field_name in required_fields,
            writable=writable,
            source_kind=source_kind,
            option_source=option_source,
        )
        all_visible_fields.append(field_runtime)

    return all_visible_fields


def _enrich_mutation_prefill_params(
    *,
    entry: Any,
    pre_fill_params: dict[str, Any],
    query_text: str,
) -> dict[str, Any]:
    """为 mutation 表单补齐轻量兜底预填值。

    功能：
        当前 LLM 提参对“新增一个健管师角色”这类创建短句并不总能稳定抽到 `roleName`。
        这里补一层确定性兜底：仅在创建类 mutation 场景、且 name-like 字段尚未命中时，
        从用户 query 中把实体名称切出来，回填到最匹配的 `xxxName` / “名称”字段。

    Args:
        entry: 当前命中的 mutation 目录项。
        pre_fill_params: LLM 已经提取出的参数。
        query_text: 用户原始自然语言。

    Returns:
        合并兜底后的参数字典；若不存在可安全推断的名称，则原样返回。

    Edge Cases:
        - 仅创建类 mutation 允许做名称兜底，避免修改类表单被错误覆盖现有主键/名称
        - 若 name-like 字段已有值，则绝不再覆盖，尊重上游提参结果
    """

    normalized = dict(pre_fill_params)
    if not _is_create_mutation_form(query_text=query_text, entry=entry):
        return normalized

    target_field = _find_create_name_target_field(entry)
    if not target_field:
        return normalized

    existing_value = normalized.get(target_field)
    if existing_value not in (None, "", [], {}):
        return normalized

    inferred_name = _infer_create_name_from_query(query_text)
    if not inferred_name:
        return normalized

    normalized[target_field] = inferred_name
    return normalized


def _should_hide_mutation_form_field(
    *,
    field_name: str,
    schema: dict[str, Any],
    hide_identifier: bool,
) -> bool:
    """判断 mutation confirm 表单里是否应隐藏当前字段。

    功能：
        request_schema 需要作为表单的主事实来源，但系统审计字段通常不属于用户确认范围。
        这里统一屏蔽创建/更新时间与删除时间；另外在“新增类 mutation”里，`id`
        往往是服务端生成字段，若继续展示会把用户误导成必须手填主键，因此单独隐藏。

    Args:
        field_name: request_schema 中的原始属性名。
        schema: 当前属性的 OpenAPI 风格定义，用于读取标题等展示信息。

    Returns:
        `True` 表示该字段不应进入 `ui_runtime.form.fields`。
    """

    normalized_name = "".join(ch for ch in field_name.lower() if ch.isalnum())
    if hide_identifier and normalized_name == "id":
        return True
    if normalized_name in _MUTATION_FORM_HIDDEN_FIELD_NAMES:
        return True

    title = str(schema.get("title") or schema.get("label") or "").strip()
    return title in _MUTATION_FORM_HIDDEN_FIELD_TITLES


def _is_create_mutation_form(*, query_text: str, entry: Any) -> bool:
    """判断当前 mutation confirm 是否属于“新增/创建”语义。

    功能：
        业务意图层当前只有通用写意图 `saveToServer`，还不足以区分“新增”和“修改”。
        为了只在创建场景隐藏自增主键，这里结合用户原始 query 与接口元数据做轻量识别。

    Args:
        query_text: 用户自然语言查询。
        entry: 当前命中的 mutation 目录项。

    Returns:
        `True` 表示当前表单更接近创建类 mutation。
    """

    normalized_query = str(query_text or "").strip().lower()
    if any(keyword in normalized_query for keyword in _CREATE_MUTATION_QUERY_KEYWORDS):
        return True

    haystack = f"{getattr(entry, 'description', '')} {getattr(entry, 'path', '')}".lower()
    return any(keyword in haystack for keyword in _CREATE_MUTATION_ENTRY_KEYWORDS)


def _find_create_name_target_field(entry: Any) -> str | None:
    """为创建类表单找到最适合承接“实体名称”的字段。"""

    schema_properties = entry.param_schema.properties if getattr(entry, "param_schema", None) else {}
    for field_name, schema in schema_properties.items():
        if not isinstance(schema, dict):
            continue
        if str(schema.get("type") or "string").lower() != "string":
            continue

        normalized_name = field_name.lower()
        title = str(schema.get("title") or schema.get("label") or "").strip()
        if normalized_name.endswith("name"):
            return field_name
        if any(keyword in title for keyword in _NAME_LIKE_FIELD_TITLE_KEYWORDS):
            return field_name
    return None


def _infer_create_name_from_query(query_text: str) -> str | None:
    """从“新增一个健管师角色”这类短句中抽取实体名称。"""

    normalized_query = " ".join(str(query_text or "").split())
    if not normalized_query:
        return None

    for pattern in _CREATE_MUTATION_NAME_PATTERNS:
        match = pattern.search(normalized_query)
        if not match:
            continue

        candidate = str(match.group("name") or "").strip().strip("“”\"'‘’：:，。,.;； ")
        candidate = re.sub(r"^(?:一个|一名|一条|名为|叫做|叫)\s*", "", candidate)
        candidate = candidate.strip()
        if candidate:
            return candidate

    return None


def _build_delete_confirm_form_fields(
    *,
    row: dict[str, Any],
    identifier_field: str,
    lookup_entry: ApiCatalogEntry | None,
) -> list[ApiQueryFormFieldRuntime]:
    """为单候选删除确认页构造只读展示字段。"""

    field_labels = lookup_entry.field_labels if lookup_entry is not None else {}
    selected_fields = _select_delete_display_fields(row, identifier_field=identifier_field)
    form_fields: list[ApiQueryFormFieldRuntime] = []
    for field_name in selected_fields:
        form_fields.append(
            ApiQueryFormFieldRuntime(
                name=field_labels.get(field_name) or field_name,
                value_type=_normalize_runtime_value_type(None, fallback_value=row.get(field_name)),
                state_path=f"/form/{field_name}",
                submit_key=field_name,
                required=field_name == identifier_field,
                writable=False,
                source_kind="context",
            )
        )
    return form_fields


def _build_delete_candidate_rows(
    *,
    rows: list[dict[str, Any]],
    identifier_field: str,
) -> list[dict[str, Any]]:
    """裁剪删除候选列表，只保留用户确认真正需要的列。"""

    if not rows:
        return []
    selected_fields = _select_delete_display_fields(rows[0], identifier_field=identifier_field)
    candidate_rows: list[dict[str, Any]] = []
    for row in rows:
        candidate_rows.append({field_name: row.get(field_name) for field_name in selected_fields})
    return candidate_rows


def _select_delete_display_fields(row: dict[str, Any], *, identifier_field: str) -> list[str]:
    """挑选删除确认和候选列表的展示列。"""

    selected_fields: list[str] = []
    for field_name in _DELETE_DISPLAY_FIELD_PRIORITY:
        actual_field = identifier_field if field_name == "id" and identifier_field in row else field_name
        if actual_field in row and actual_field not in selected_fields:
            selected_fields.append(actual_field)

    for field_name in row:
        if field_name == identifier_field and field_name not in selected_fields:
            selected_fields.append(field_name)
        elif field_name.lower().endswith("name") and field_name not in selected_fields:
            selected_fields.append(field_name)
        elif field_name.lower().endswith("code") and field_name not in selected_fields:
            selected_fields.append(field_name)
        elif field_name.lower() == "status" and field_name not in selected_fields:
            selected_fields.append(field_name)
        if len(selected_fields) >= 5:
            break

    if not selected_fields:
        selected_fields = [identifier_field] if identifier_field in row else list(row.keys())[:4]
    return selected_fields


def _build_delete_submit_payload(
    *,
    delete_entry: ApiCatalogEntry,
    row: dict[str, Any],
    identifier_field: str,
) -> dict[str, Any]:
    """为单候选删除确认页构造最终提交 payload。"""

    payload_key = _resolve_delete_payload_key(delete_entry, identifier_field=identifier_field)
    identifier_value = row.get(identifier_field)
    schema = delete_entry.param_schema.properties.get(payload_key, {})
    if str(schema.get("type") or "").lower() == "array":
        return {payload_key: [identifier_value]}
    return {payload_key: identifier_value}


def _build_delete_row_payload_template(
    *,
    delete_entry: ApiCatalogEntry,
    identifier_field: str,
) -> dict[str, Any]:
    """为多候选删除行按钮构造按行取值的 payload 模板。"""

    payload_key = _resolve_delete_payload_key(delete_entry, identifier_field=identifier_field)
    schema = delete_entry.param_schema.properties.get(payload_key, {})
    if str(schema.get("type") or "").lower() == "array":
        return {payload_key: [{"$bindRow": identifier_field}]}
    return {payload_key: {"$bindRow": identifier_field}}


def _resolve_delete_payload_key(delete_entry: ApiCatalogEntry, *, identifier_field: str) -> str:
    """为删除接口确定最合理的主键入参名。"""

    schema_properties = delete_entry.param_schema.properties
    preferred_keys = [field_name for field_name in schema_properties if field_name.lower() in {"id", "ids"}]
    preferred_keys.extend(
        [field_name for field_name in schema_properties if field_name.lower().endswith("id")]
    )
    if preferred_keys:
        return preferred_keys[0]
    return identifier_field or "id"


def _build_runtime_actions(
    action_codes: set[str] | None,
    *,
    ui_catalog_service: UICatalogService,
) -> list[ApiQueryUIAction]:
    """按当前运行时启用状态构造 UI 动作定义。"""

    return ui_catalog_service.build_runtime_actions(action_codes)


def _infer_param_source(method: str | None) -> str:
    """推导当前接口参数的承载位置。"""

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
        列表筛选区只展示对用户有意义的业务过滤字段，分页控制字段和内部保留字段不应直接暴露
        给前端筛选表单。

    Edge Cases:
        - 当前接口声明的 page/pageSize 字段会与全局排除集一起过滤，避免重复暴露
        - 标签优先取 title/label，保证前端不必再猜字段中文名
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
    ui_catalog_service: UICatalogService,
) -> ApiQueryUIRuntime:
    """根据接口元数据和执行结果推导前端运行时契约。

    功能：
        `/api-query` 已不再把 `ui_runtime` 直接暴露给前端执行二跳，但内部仍需要一份稳定
        运行时事实来驱动 UI 生成、动作白名单和 patch/detail 能力判定。

    Edge Cases:
        - detail/list 是否启用不仅取决于目录 hint，还要结合实际数据形态和执行状态
        - 多步骤汇总结果不会误启详情/分页能力，避免前端把摘要表当单接口列表继续查询
        - preserve_on_pagination 会主动排除分页字段和 id，避免二跳请求把旧定位参数重复透传
    """

    rows = _normalize_rows(execution_result.data)
    action_codes = {"refresh", "export"}
    param_source = _infer_param_source(entry.method)

    detail_hint = entry.detail_hint
    identifier_field = detail_hint.identifier_field or _infer_identifier_field(rows)
    detail_enabled = (
        execution_result.status == ApiQueryExecutionStatus.SUCCESS
        and bool(identifier_field)
        and (detail_hint.enabled or identifier_field is not None)
    )

    # 分页和筛选能力来自目录 hint + 执行事实双重判定，不能只看 schema 是否“像列表”。
    pagination_hint = entry.pagination_hint
    page_param = pagination_hint.page_param or "pageNum"
    page_size_param = pagination_hint.page_size_param or "pageSize"
    filter_fields = _build_list_filter_fields(entry, page_param=page_param, page_size_param=page_size_param)
    is_list_payload = isinstance(execution_result.data, list)
    pagination_enabled = (
        execution_result.status in {ApiQueryExecutionStatus.SUCCESS, ApiQueryExecutionStatus.EMPTY}
        and (pagination_hint.enabled or execution_result.total > len(rows))
        and (execution_result.total > 0 or bool(rows))
    )
    list_enabled = execution_result.status in {ApiQueryExecutionStatus.SUCCESS, ApiQueryExecutionStatus.EMPTY} and (
        is_list_payload or pagination_enabled or bool(filter_fields)
    )

    requested_component_codes = [
        "PlannerCard",
        "PlannerMetric",
        "PlannerInfoGrid",
        "PlannerTable",
        "PlannerDetailCard",
        "PlannerNotice",
        "PlannerPagination",
    ]
    if list_enabled:
        requested_component_codes.extend(["PlannerForm", "PlannerInput", "PlannerButton"])
    if _has_write_business_intent(business_intents):
        requested_component_codes.extend(["PlannerForm", "PlannerInput", "PlannerSelect", "PlannerButton"])
    components = ui_catalog_service.get_component_codes(intent="query", requested_codes=requested_component_codes)

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
        ui_actions=_build_runtime_actions(action_codes, ui_catalog_service=ui_catalog_service),
        list=ApiQueryListRuntime(
            enabled=list_enabled,
            api_id=list_api_id if list_enabled else None,
            route_url="/api/v1/api-query" if list_enabled else None,
            ui_action=(pagination_hint.ui_action or "remoteQuery") if list_enabled else None,
            param_source=param_source if list_enabled else None,
            request_schema_fields=list(entry.param_schema.properties) if list_enabled else None,
            pagination=ApiQueryListPaginationRuntime(
                enabled=pagination_enabled,
                total=execution_result.total,
                page_size=_infer_page_size(params, len(rows)),
                current_page=_infer_current_page(params, page_param=page_param),
                page_param=page_param if list_enabled else None,
                page_size_param=page_size_param if list_enabled else None,
                mutation_target=pagination_hint.mutation_target if pagination_enabled else None,
            ),
            filters=ApiQueryListFiltersRuntime(enabled=bool(filter_fields), fields=filter_fields),
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
                request_schema_fields=(
                    [(detail_hint.query_param or identifier_field)]
                    if detail_enabled and (detail_hint.query_param or identifier_field)
                    else None
                ),
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


async def _enrich_detail_runtime_request_schema(
    runtime: ApiQueryUIRuntime,
    *,
    registry_source: ApiCatalogRegistrySource,
) -> ApiQueryUIRuntime:
    """按详情接口自己的 request_schema 修正详情请求参数键。"""

    if not runtime.detail.enabled or not runtime.detail.api_id:
        return runtime

    try:
        detail_entry = await registry_source.get_entry_by_id(runtime.detail.api_id)
    except Exception as exc:  # pragma: no cover - 依赖外部治理源状态的兜底分支
        logger.warning(
            "api_query failed to load detail request_schema api_id=%s error=%s",
            runtime.detail.api_id,
            exc,
        )
        return runtime

    if detail_entry is None:
        return runtime

    resolved_identifier_param = _resolve_detail_identifier_param(
        detail_entry=detail_entry,
        preferred_param=runtime.detail.request.identifier_param,
        source_identifier_field=runtime.detail.source.identifier_field,
    )
    return runtime.model_copy(
        update={
            "detail": runtime.detail.model_copy(
                update={
                    "request": runtime.detail.request.model_copy(
                        update={
                            "identifier_param": resolved_identifier_param,
                            "request_schema_fields": list(detail_entry.param_schema.properties),
                        }
                    )
                }
            )
        }
    )


def _resolve_detail_identifier_param(
    *,
    detail_entry: ApiCatalogEntry,
    preferred_param: str | None,
    source_identifier_field: str | None,
) -> str | None:
    """选择一个真实存在于详情接口 request_schema 中的参数键。"""

    schema_properties = list(detail_entry.param_schema.properties)
    if not schema_properties:
        return preferred_param or source_identifier_field

    if preferred_param in schema_properties:
        return preferred_param
    if source_identifier_field in schema_properties:
        return source_identifier_field

    id_like_fields = [
        field_name
        for field_name in schema_properties
        if field_name.lower() in {"id", "ids"} or field_name.lower().endswith("id")
    ]
    if id_like_fields:
        return id_like_fields[0]

    for required_field in detail_entry.param_schema.required:
        if required_field in detail_entry.param_schema.properties:
            return required_field

    return schema_properties[0]


async def _enrich_runtime_from_ui_spec(
    runtime: ApiQueryUIRuntime,
    ui_spec: dict[str, Any] | None,
    *,
    business_intents: list[ApiQueryBusinessIntent],
    trace_id: str,
    registry_source: ApiCatalogRegistrySource,
) -> ApiQueryUIRuntime:
    """根据最终 `ui_spec` 反推表单提交契约。"""

    form_contract = await _extract_form_runtime_from_spec(
        ui_spec,
        business_intents=business_intents,
        trace_id=trace_id,
        registry_source=registry_source,
    )
    if not form_contract.enabled:
        return runtime
    return runtime.model_copy(update={"form": form_contract})


async def _extract_form_runtime_from_spec(
    ui_spec: dict[str, Any] | None,
    *,
    business_intents: list[ApiQueryBusinessIntent],
    trace_id: str,
    registry_source: ApiCatalogRegistrySource,
) -> ApiQueryFormRuntime:
    """从最终 Spec 中提取表单运行时契约。

    功能：
        规则渲染和 LLM 渲染最终都只输出 `ui_spec`，因此若后续还需要恢复表单提交契约，
        就必须在这一层从真实渲染结果反推。这样可以确保最终暴露的 form runtime 与页面
        实际字段一致，而不是和理论 schema 脱节。

    Edge Cases:
        - 没有写意图、没有 remoteMutation、或 `body/queryParams` 不含 `$bindState` 时都会直接视为“无表单”
        - 治理源查询失败不会让整个响应失败，只会回退到最小表单契约
        - 未出现在交互组件中的绑定会被视为只读上下文字段，避免误标为可编辑输入
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
    request_params = action_params.get("body")
    if not isinstance(request_params, dict) or not request_params:
        request_params = action_params.get("queryParams")
    if not isinstance(api_id, str) or not api_id.strip() or not isinstance(request_params, dict):
        return ApiQueryFormRuntime()

    mutation_entry: ApiCatalogEntry | None = None
    try:
        mutation_entry = await registry_source.get_entry_by_id(api_id)
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
    for submit_key, submit_value in request_params.items():
        if not isinstance(submit_value, dict):
            continue
        state_path = submit_value.get("$bindState")
        if not isinstance(state_path, str) or not state_path.startswith("/"):
            continue

        bind_paths.append(state_path)
        # 绑定路径是否出现在交互组件里，决定了这个字段应被视为用户输入还是只读上下文。
        binding_meta = interactive_bindings.get(state_path, {})
        component_type = binding_meta.get("component_type")
        source_kind = "user_input"
        writable = True
        if component_type == "PlannerSelect":
            source_kind = "dictionary"
        elif component_type is None:
            source_kind = "context"
            writable = False

        state_value = read_state_value(state, state_path)
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
        # generated spec 只能声明 `api_id`；真正可执行的提交地址要回到统一配置模板，
        # 这样不同环境、灰度域名和回滚切换都不会散落到 renderer 契约里。
        route_url=_build_runtime_invoke_url(api_id),
        ui_action="remoteMutation",
        request_schema_fields=list(property_schemas),
        state_path=_infer_form_state_root(bind_paths),
        fields=form_fields,
        submit=ApiQueryFormSubmitRuntime(business_intent=write_intent.code, confirm_required=True),
    )


def _collect_form_input_bindings(ui_spec: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """收集表单输入组件的 `$bindState` 路径与字段来源元数据。"""

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
                    "option_source": _extract_form_option_source(
                        dict_code=props.get("dictCode"),
                        options_payload=props.get("options"),
                    ),
                }
    return bindings


def _build_runtime_invoke_url(api_id: str) -> str:
    """根据统一模板构造 runtime invoke URL。

    功能：
        `form.route_url` 要表达的是“前端真正应该 POST 到哪里”，因此必须和执行器侧
        使用同一份 `api_query_runtime_invoke_url_template`。这样才能保证：

        1. 前端确认提交与网关执行器命中同一 runtime 入口
        2. 多环境灰度/回滚只改配置，不改 renderer 或前端组装逻辑

    Args:
        api_id: `ui_endpoints.id`，用于替换模板中的 `{id}` 占位符。

    Returns:
        可直接提交的 runtime invoke URL。

    Raises:
        RuntimeError: 当配置模板缺少 `{id}` 占位符时抛出，避免返回不可执行的假 URL。
    """

    try:
        return settings.api_query_runtime_invoke_url_template.format(id=api_id)
    except KeyError as exc:
        raise RuntimeError("API_QUERY_RUNTIME_INVOKE_URL_TEMPLATE 缺少 {id} 占位符") from exc


def _normalize_response_created_by(user_context: dict[str, Any]) -> str:
    """从请求级用户上下文提取前端二跳元数据里的 `createdBy`。"""

    raw_user_id = user_context.get("userId")
    if raw_user_id is None:
        return ""
    normalized_user_id = str(raw_user_id).strip()
    return normalized_user_id


def _extract_form_option_source(
    *,
    dict_code: Any = None,
    options_payload: Any = None,
) -> ApiQueryFormOptionSourceRuntime | None:
    """从 `PlannerSelect` 组件属性推导可复用的选项来源契约。

    优先使用 `props.dictCode`（与 json-render 契约对齐），同时兼容历史 `props.options`。
    """

    if isinstance(dict_code, str) and dict_code.strip():
        return ApiQueryFormOptionSourceRuntime(type="dict", dict_code=dict_code.strip())

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


def _build_prefilled_form_state(
    *,
    fields: list[ApiQueryFormFieldRuntime],
    pre_fill_params: dict[str, Any],
) -> dict[str, Any]:
    """根据字段绑定路径和提取结果构造表单初始 state。

    功能：
        json-render 读取初始值依赖的是嵌套 `state`，而不是 `execution_plan.params`。
        这里统一把 `submit_key -> state_path` 映射折叠成真实的 JSON 结构，避免再把
        `/form/email` 误写成 `{\"form/email\": ...}` 这种扁平键。
    """

    state: dict[str, Any] = {}
    for field in fields:
        write_state_value(
            state,
            field.state_path,
            pre_fill_params.get(field.submit_key),
        )
    return state


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
    *,
    ui_catalog_service: UICatalogService,
) -> ApiQueryUIRuntime:
    """用最终生成的 UI Spec 回填组件与动作清单。"""

    action_codes = {action.code for action in base_runtime.ui_actions}
    action_codes.update(_collect_action_types(ui_spec, ui_catalog_service=ui_catalog_service))
    components = _collect_component_types(ui_spec) or base_runtime.components
    return base_runtime.model_copy(
        update={
            "components": components,
            "ui_actions": _build_runtime_actions(action_codes, ui_catalog_service=ui_catalog_service),
        }
    )


def _finalize_render_runtime(
    base_runtime: ApiQueryUIRuntime,
    ui_spec: dict[str, Any] | None,
    build_result: UISpecBuildResult,
    *,
    ui_catalog_service: UICatalogService,
) -> ApiQueryUIRuntime:
    """根据第五阶段结果收口最终运行时契约。"""

    finalized_runtime = _finalize_ui_runtime(base_runtime, ui_spec, ui_catalog_service=ui_catalog_service)
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
    """递归收集 UI Spec 中出现的组件类型。"""

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


def _collect_action_types(node: Any, *, ui_catalog_service: UICatalogService) -> set[str]:
    """递归收集 UI Spec 中出现的动作类型。"""

    action_types: set[str] = set()
    known_action_codes = ui_catalog_service.get_all_action_codes()
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
    """递归扫描动作定义载荷。"""

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
    for exact in ("id", "code", "uuid"):
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


def _infer_current_page(params: dict[str, Any], *, page_param: str | None = None) -> int | None:
    """从查询参数中推断当前页码。"""

    candidate_keys: list[str] = []
    if page_param:
        candidate_keys.append(page_param)
    candidate_keys.extend(["page", "pageNum", "pageNo", "page_no", "pageIndex", "current"])
    for key in candidate_keys:
        value = params.get(key)
        if isinstance(value, int) and value > 0:
            return value
    return None


def _build_plan_context_pool(execution_report: DagExecutionReport) -> dict[str, ApiQueryContextStepResult]:
    """将第三阶段执行报告转换成多步骤 `context_pool`。"""

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
    """将多步骤执行结果收敛成对外主状态。"""
    ordered_records = [
        execution_report.records_by_step_id[step_id]
        for step_id in execution_report.execution_order
        if step_id in execution_report.records_by_step_id
    ]
    statuses = [record.execution_result.status for record in ordered_records]
    if not statuses:
        return ApiQueryExecutionStatus.SKIPPED

    if _is_wait_select_execution_report(execution_report, ordered_records=ordered_records):
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


def _is_wait_select_execution_report(
    execution_report: DagExecutionReport,
    *,
    ordered_records: list[DagStepExecutionRecord],
) -> bool:
    """判断执行报告是否命中 user_select 等待态。"""

    if not ordered_records:
        return False
    step_ids = [record.step.step_id for record in ordered_records]
    records_by_step_id = execution_report.records_by_step_id

    for record in ordered_records:
        result = record.execution_result
        if result.status != ApiQueryExecutionStatus.SKIPPED:
            continue
        if result.error_code != "WAIT_SELECT_REQUIRED":
            continue
        if not any(dep in records_by_step_id for dep in record.step.depends_on):
            continue
        if any(
            records_by_step_id[step_id].execution_result.status == ApiQueryExecutionStatus.ERROR
            for step_id in step_ids
            if step_id in records_by_step_id
        ):
            return False
        return True
    return False


def _select_response_anchor(execution_report: DagExecutionReport) -> DagStepExecutionRecord | None:
    """选择对外响应锚点步骤。"""

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
) -> _QueryUISelection:
    """为查询读态挑选主数据与渲染模式。"""
    return _select_query_ui_payload(execution_report, anchor_record, multi_step_render_policy="summary_table")


def _build_wait_select_rows(execution_report: DagExecutionReport) -> list[dict[str, Any]]:
    """抽取 WAIT_SELECT_REQUIRED 的候选列表数据。"""
    for step_id in execution_report.execution_order:
        record = execution_report.records_by_step_id[step_id]
        execution_result = record.execution_result
        if execution_result.error_code != "WAIT_SELECT_REQUIRED":
            continue
        options_by_binding = execution_result.meta.get("options_by_binding")
        if not isinstance(options_by_binding, dict):
            continue
        rows: list[dict[str, Any]] = []
        for binding_key, options in options_by_binding.items():
            if not isinstance(options, list):
                continue
            for index, value in enumerate(options[:_SELECT_CANDIDATE_ROW_LIMIT], start=1):
                rows.append(
                    {
                        "bindingKey": binding_key,
                        "candidateIndex": index,
                        "candidateValue": value,
                        "bindingMap": {binding_key: value},
                    }
                )
        return rows
    return []


def _build_wait_select_row_actions(execution_report: DagExecutionReport) -> list[dict[str, Any]]:
    """构建 WAIT_SELECT 场景的行级动作。"""
    wait_rows = _build_wait_select_rows(execution_report)
    if not wait_rows:
        return []
    return [
        {
            "action": "remoteQuery",
            "label": "使用该值继续",
            "params": {
                "api": "/api/v1/api-query",
                "queryParams": {},
                "body": {
                    "selection_context": {
                        "user_select": {"$bindRow": "bindingMap"}
                    }
                },
            },
        }
    ]


def _build_wait_select_context_pool(execution_report: DagExecutionReport) -> dict[str, ApiQueryContextStepResult]:
    """为 WAIT_SELECT 场景构建结构化上下文。"""
    for step_id in execution_report.execution_order:
        record = execution_report.records_by_step_id[step_id]
        result = record.execution_result
        if result.error_code != "WAIT_SELECT_REQUIRED":
            continue
        return {
            step_id: ApiQueryContextStepResult(
                status=ApiQueryExecutionStatus.SKIPPED,
                domain=record.entry.domain,
                api_id=record.entry.id,
                api_path=record.entry.path,
                method=record.entry.method,
                data=[],
                total=0,
                error=ApiQueryExecutionErrorDetail(
                    code=result.error_code,
                    message=result.error or "命中多个候选值，请先选择后继续。",
                    retryable=True,
                ),
                skipped_reason=result.skipped_reason,
                meta=dict(result.meta),
            )
        }
    return {}


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


def _build_runtime_from_execution_report(
    execution_report: DagExecutionReport,
    anchor_record: DagStepExecutionRecord | None,
    *,
    business_intents: list[ApiQueryBusinessIntent],
    ui_catalog_service: UICatalogService,
    runtime_anchor_record: DagStepExecutionRecord | None = None,
) -> ApiQueryUIRuntime:
    """根据执行报告推导前端运行时契约。"""
    wait_select_runtime = _build_wait_select_runtime(
        execution_report,
        ui_catalog_service=ui_catalog_service,
    )
    if wait_select_runtime is not None:
        return wait_select_runtime

    # 终态渲染时 runtime 必须绑定到同一条业务记录，避免“展示终态数据 + 多步骤默认能力”错配触发 Guard 冻结。
    resolved_runtime_anchor = runtime_anchor_record
    if resolved_runtime_anchor is None and len(execution_report.records_by_step_id) == 1:
        resolved_runtime_anchor = anchor_record

    if resolved_runtime_anchor is not None:
        return _build_ui_runtime(
            resolved_runtime_anchor.entry,
            resolved_runtime_anchor.execution_result,
            params=resolved_runtime_anchor.resolved_params,
            business_intents=business_intents,
            ui_catalog_service=ui_catalog_service,
        )
    return ApiQueryUIRuntime(
        components=ui_catalog_service.get_component_codes(
            intent="query",
            requested_codes=["PlannerCard", "PlannerTable", "PlannerForm", "PlannerPagination", "PlannerNotice"],
        ),
        ui_actions=_build_runtime_actions({"refresh", "export"}, ui_catalog_service=ui_catalog_service),
    )


def _build_wait_select_runtime(
    execution_report: DagExecutionReport,
    *,
    ui_catalog_service: UICatalogService,
) -> ApiQueryUIRuntime | None:
    """构建 user_select 等待态运行时。"""
    for step_id in execution_report.execution_order:
        record = execution_report.records_by_step_id[step_id]
        execution_result = record.execution_result
        if execution_result.error_code != "WAIT_SELECT_REQUIRED":
            continue
        options_by_binding = execution_result.meta.get("options_by_binding")
        if not isinstance(options_by_binding, dict) or not options_by_binding:
            return None

        return ApiQueryUIRuntime(
            components=ui_catalog_service.get_component_codes(
                intent="query",
                requested_codes=["PlannerCard", "PlannerTable", "PlannerNotice"],
            ),
            ui_actions=_build_runtime_actions({"remoteQuery", "refresh"}, ui_catalog_service=ui_catalog_service),
            list=ApiQueryListRuntime(
                enabled=True,
                route_url="/api/v1/api-query",
                ui_action="remoteQuery",
            ),
            detail=ApiQueryDetailRuntime(enabled=False),
            form=ApiQueryFormRuntime(enabled=False),
            audit=ApiQueryUIRuntime().audit,
        )
    return None


def _resolve_multi_step_render_policy(raw_policy: str | None) -> str:
    """解析多步骤渲染策略，非法值统一回退到兼容策略。"""

    policy = str(raw_policy or "").strip().lower()
    if policy in _SUPPORTED_MULTI_STEP_RENDER_POLICIES:
        return policy
    return _DEFAULT_MULTI_STEP_RENDER_POLICY


def _select_query_ui_payload(
    execution_report: DagExecutionReport,
    anchor_record: DagStepExecutionRecord | None,
    *,
    multi_step_render_policy: str,
) -> _QueryUISelection:
    """按策略选择查询读态的主数据载荷。

    约束：
        1. WAIT_SELECT_REQUIRED 始终优先，避免被策略分支绕开。
        2. 多步骤默认采用 terminal_result，直接展示最后一个成功步骤的数据。
        3. composite_result 在规则渲染阶段先回退到 terminal_result，后续可叠加 LLM 组合视图。
        4. aggregate_result 会把多步骤业务结果聚合成一个复合对象，供 Renderer 同屏拆块展示。
        5. auto_result 会在 terminal 与 aggregate 之间自动选择，兼顾“终态优先”与“多块并列展示”。
    """
    wait_select_rows = _build_wait_select_rows(execution_report)
    if wait_select_rows:
        return _QueryUISelection(
            data_for_ui=wait_select_rows,
            render_mode="table",
            source="wait_select_candidates",
        )

    if len(execution_report.records_by_step_id) <= 1:
        if anchor_record is None:
            return _QueryUISelection(data_for_ui=[], render_mode="table", source="empty")
        rows = _normalize_data_for_ui(anchor_record.execution_result)
        return _QueryUISelection(
            data_for_ui=rows,
            render_mode=_infer_render_mode_from_rows(rows, anchor_record),
            source="single_step_anchor",
            runtime_anchor_record=anchor_record,
        )

    if multi_step_render_policy == "summary_table":
        summary_rows = _build_multi_step_summary_rows(execution_report)
        return _QueryUISelection(
            data_for_ui=summary_rows,
            render_mode="summary_table",
            source="multi_step_summary",
            runtime_anchor_record=None,
        )

    if multi_step_render_policy == "aggregate_result":
        aggregated_payload, aggregate_label_index = _build_multi_step_aggregate_payload(execution_report)
        if aggregated_payload:
            return _build_multi_step_aggregate_selection(
                aggregated_payload=aggregated_payload,
                aggregate_label_index=aggregate_label_index,
                source="multi_step_aggregate",
            )

    terminal_record = _select_terminal_business_record(execution_report, anchor_record)
    if multi_step_render_policy == "auto_result":
        aggregated_payload, aggregate_label_index = _build_multi_step_aggregate_payload(execution_report)
        if _should_use_aggregate_result(execution_report, aggregated_payload):
            return _build_multi_step_aggregate_selection(
                aggregated_payload=aggregated_payload,
                aggregate_label_index=aggregate_label_index,
                source="multi_step_auto_aggregate",
            )
        if terminal_record is not None:
            return _build_terminal_selection(terminal_record)
        if aggregated_payload:
            return _build_multi_step_aggregate_selection(
                aggregated_payload=aggregated_payload,
                aggregate_label_index=aggregate_label_index,
                source="multi_step_auto_aggregate_fallback",
            )
        summary_rows = _build_multi_step_summary_rows(execution_report)
        return _QueryUISelection(
            data_for_ui=summary_rows,
            render_mode="summary_table",
            source="multi_step_summary_fallback",
            runtime_anchor_record=None,
        )

    if terminal_record is not None:
        return _build_terminal_selection(terminal_record)

    # 当 terminal/composite 找不到可展示业务数据时，回退到步骤汇总表保证可解释性。
    summary_rows = _build_multi_step_summary_rows(execution_report)
    return _QueryUISelection(
        data_for_ui=summary_rows,
        render_mode="summary_table",
        source="multi_step_summary_fallback",
        runtime_anchor_record=None,
    )


def _build_terminal_selection(record: DagStepExecutionRecord) -> _QueryUISelection:
    """把终态 record 折叠成统一的 QueryUISelection。"""

    rows = _normalize_data_for_ui(record.execution_result)
    return _QueryUISelection(
        data_for_ui=rows,
        render_mode=_infer_render_mode_from_rows(rows, record),
        source=f"terminal:{record.step.step_id}",
        runtime_anchor_record=record,
    )


def _build_multi_step_aggregate_selection(
    *,
    aggregated_payload: dict[str, Any],
    aggregate_label_index: dict[str, str],
    source: str,
) -> _QueryUISelection:
    """构造聚合渲染选择对象。"""

    return _QueryUISelection(
        data_for_ui=[aggregated_payload],
        render_mode="composite",
        source=source,
        runtime_anchor_record=None,
        response_field_label_index=aggregate_label_index,
    )


def _should_use_aggregate_result(
    execution_report: DagExecutionReport,
    aggregated_payload: dict[str, Any],
) -> bool:
    """判断 auto_result 是否应切换到 aggregate 渲染。

    策略：
        - 至少存在 2 个叶子业务步骤；
        - 且当前可渲染的聚合 section 至少 2 个。
    """

    if not aggregated_payload:
        return False
    leaf_step_count = len(_collect_leaf_step_ids(execution_report))
    section_count = len(aggregated_payload)
    return leaf_step_count >= 2 and section_count >= 2


def _build_multi_step_aggregate_payload(
    execution_report: DagExecutionReport,
) -> tuple[dict[str, Any], dict[str, str]]:
    """聚合同一执行链路中的多步骤结果，供 composite 渲染同屏展示。

    设计意图：
        - terminal_result 只保留最后一步，适合“链路末端即最终答案”的场景；
        - aggregate_result 需要把每个业务步骤都保留为独立 section，保证“健康基本信息 + 病史 + 体检”
          等并列语义不会在 UI 端被截断为单锚点结果。
    """

    preferred_statuses = {
        ApiQueryExecutionStatus.SUCCESS,
        ApiQueryExecutionStatus.PARTIAL_SUCCESS,
        ApiQueryExecutionStatus.EMPTY,
    }
    leaf_step_ids = _collect_leaf_step_ids(execution_report)
    payload: dict[str, Any] = {}
    label_index: dict[str, str] = {}
    section_key_counter: dict[str, int] = {}

    for step_id in execution_report.execution_order:
        # 聚合视图只展示“终态业务块”，跳过客户识别、参数准备等上游依赖步骤，
        # 避免出现“4 步执行只想看 3 块业务结果”时把中间跳板步骤也渲染出来。
        if leaf_step_ids and step_id not in leaf_step_ids:
            continue
        record = execution_report.records_by_step_id[step_id]
        if record.execution_result.status not in preferred_statuses:
            continue

        rows = _normalize_data_for_ui(record.execution_result)
        if not rows:
            continue

        # section key 直接对齐业务接口尾段（如 healthBasic / physicalExam），
        # 让前端可以稳定把 child 与后端字段做一一映射。
        section_key = _build_aggregate_section_key(record, section_key_counter)
        payload[section_key] = rows

        section_title = _build_aggregate_section_title(record, fallback=section_key)
        if section_title:
            label_index.setdefault(section_key, section_title)

        # 同时合并每个步骤的字段标签，保障聚合视图中的列标题仍能展示业务中文名。
        step_label_index = _build_response_field_label_index(record)
        for field_path, label in step_label_index.items():
            if "[]" in field_path:
                leaf_path = field_path.split("[]", 1)[-1].lstrip(".")
                if leaf_path:
                    label_index.setdefault(leaf_path, label)
                    label_index.setdefault(f"{section_key}[].{leaf_path}", label)
                continue
            if "." in field_path:
                leaf_path = field_path.split(".", 1)[-1]
                label_index.setdefault(leaf_path, label)
                label_index.setdefault(f"{section_key}[].{leaf_path}", label)
                continue
            label_index.setdefault(field_path, label)
            label_index.setdefault(f"{section_key}[].{field_path}", label)

    return payload, label_index


def _collect_leaf_step_ids(execution_report: DagExecutionReport) -> set[str]:
    """计算执行计划中的叶子步骤（没有被其他步骤依赖的 step）。"""

    all_step_ids = {step.step_id for step in execution_report.plan.steps}
    depended_step_ids: set[str] = set()
    for step in execution_report.plan.steps:
        for depended_step_id in step.depends_on:
            if depended_step_id in all_step_ids:
                depended_step_ids.add(depended_step_id)
    leaf_step_ids = all_step_ids - depended_step_ids
    return leaf_step_ids


def _build_aggregate_section_key(
    record: DagStepExecutionRecord,
    section_key_counter: dict[str, int],
) -> str:
    """生成聚合渲染 section 键名，优先复用业务接口尾段。"""

    api_tail = record.entry.path.rsplit("/", 1)[-1] if isinstance(record.entry.path, str) else ""
    base_key = api_tail.strip() if api_tail.strip() else record.step.step_id
    # 统一清洗非法字符，避免 path 中的连字符、空格等破坏字段路径拼接。
    normalized_key = re.sub(r"[^0-9a-zA-Z_]", "_", base_key)
    if not normalized_key:
        normalized_key = re.sub(r"[^0-9a-zA-Z_]", "_", record.step.step_id) or "section"

    current_index = section_key_counter.get(normalized_key, 0) + 1
    section_key_counter[normalized_key] = current_index
    if current_index == 1:
        return normalized_key
    return f"{normalized_key}_{current_index}"


def _build_aggregate_section_title(
    record: DagStepExecutionRecord,
    *,
    fallback: str,
) -> str:
    """推断聚合 section 的展示标题。"""

    description = (record.entry.description or "").strip()
    if description:
        return description
    return fallback


def _select_terminal_business_record(
    execution_report: DagExecutionReport,
    anchor_record: DagStepExecutionRecord | None,
) -> DagStepExecutionRecord | None:
    """选择多步骤业务终态记录。"""

    preferred_statuses = (
        ApiQueryExecutionStatus.SUCCESS,
        ApiQueryExecutionStatus.PARTIAL_SUCCESS,
        ApiQueryExecutionStatus.EMPTY,
    )
    for step_id in reversed(execution_report.execution_order):
        record = execution_report.records_by_step_id[step_id]
        if record.execution_result.status not in preferred_statuses:
            continue
        if _normalize_data_for_ui(record.execution_result):
            return record
        if record.execution_result.status == ApiQueryExecutionStatus.EMPTY:
            return record

    if anchor_record is None:
        return None
    if _normalize_data_for_ui(anchor_record.execution_result):
        return anchor_record
    return None


def _build_multi_step_summary_rows(execution_report: DagExecutionReport) -> list[dict[str, Any]]:
    """构造多步骤执行汇总行。"""
    summary_rows: list[dict[str, Any]] = []
    for step_id in execution_report.execution_order:
        record = execution_report.records_by_step_id[step_id]
        _, shaped_meta = _shape_context_data(record.execution_result.data)
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


def _infer_render_mode_from_rows(
    rows: list[dict[str, Any]],
    record: DagStepExecutionRecord | None,
) -> str:
    """根据行数据形态推断渲染模式。"""
    if not rows:
        return "table"
    if len(rows) == 1 and record is not None and isinstance(record.execution_result.data, dict):
        if _has_nested_business_blocks(record.execution_result.data):
            # 单对象中同时包含概览块与明细集合时，继续走 detail 会把复杂结构字符串化。
            # 这里显式切到 composite，让下游规则渲染按“指标 + 表格”语义拆分展示。
            return "composite"
        return "detail"
    return "table"


def _has_nested_business_blocks(payload: dict[str, Any]) -> bool:
    """判断单对象结果是否包含可拆分的复合业务块。"""

    for value in payload.values():
        if isinstance(value, dict) and value:
            return True
        if isinstance(value, list) and any(isinstance(item, dict) for item in value):
            return True
    return False


def _infer_query_render_mode(
    execution_report: DagExecutionReport,
    anchor_record: DagStepExecutionRecord | None,
) -> str:
    """推断当前查询结果应使用的读态渲染模式。"""

    return _select_query_ui_payload(
        execution_report,
        anchor_record,
        multi_step_render_policy="summary_table",
    ).render_mode


def _build_execution_title(execution_report: DagExecutionReport, anchor_record: DagStepExecutionRecord | None) -> str:
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
        if record.execution_result.status == ApiQueryExecutionStatus.SKIPPED:
            return _build_skip_message(record.execution_result)
    return "由于缺少必要条件，当前查询未被执行。"


def _build_response_execution_plan(
    plan: ApiQueryExecutionPlan,
    step_entries: dict[str, ApiCatalogEntry],
) -> ApiQueryExecutionPlan:
    """为响应层补齐步骤级 `api_id`。"""

    enriched_steps = []
    for step in plan.steps:
        entry = step_entries.get(step.step_id)
        enriched_steps.append(step.model_copy(update={"api_id": entry.id if entry else step.api_id}))
    return plan.model_copy(update={"steps": enriched_steps})


def _build_response_field_label_index(
    runtime_anchor_record: DagStepExecutionRecord | None,
) -> dict[str, str]:
    """根据终态 record 的 response_schema 构建字段显示名索引。

    功能：
        ui_spec 中的 `label/title` 需要展示业务语义文案，而不是原始字段键名。
        这里统一把 schema 的 description/title 展开成稳定索引，供 Renderer 在
        `PlannerMetric / PlannerTable / PlannerDetailCard` 三类组件中复用。

    返回键规范：
        - 顶层字段：`field`
        - 嵌套对象字段：`parent.child`
        - 数组对象字段：`listField[].child`
    """

    if runtime_anchor_record is None:
        return {}
    entry = runtime_anchor_record.entry
    response_schema = entry.response_schema
    if not isinstance(response_schema, dict) or not response_schema:
        return _normalize_entry_field_labels(entry.field_labels)

    for schema_node in _iter_response_schema_label_nodes(response_schema, entry.response_data_path):
        label_index: dict[str, str] = {}
        _collect_schema_field_labels(schema_node, label_index, prefix="")
        if label_index:
            return _merge_label_index_with_entry_labels(label_index, entry.field_labels)

    return _normalize_entry_field_labels(entry.field_labels)


def _iter_response_schema_label_nodes(
    response_schema: dict[str, Any],
    response_data_path: str,
):
    """按声明路径优先、候选路径兜底返回可用于抽取 label 的 schema 节点。"""

    candidates: list[str] = []
    preferred_path = (response_data_path or "").strip()
    if preferred_path:
        candidates.append(preferred_path)
    for fallback_path in _RESPONSE_SCHEMA_FALLBACK_PATHS:
        if fallback_path not in candidates:
            candidates.append(fallback_path)
    if not candidates:
        candidates.append("")

    seen: set[str] = set()
    for path in candidates:
        if path in seen:
            continue
        seen.add(path)
        schema_node, _ = resolve_schema_at_data_path(response_schema, path)
        if isinstance(schema_node, dict) and schema_node:
            yield schema_node


def _normalize_entry_field_labels(field_labels: dict[str, str]) -> dict[str, str]:
    """过滤并标准化 catalog `field_labels`。"""

    normalized: dict[str, str] = {}
    if not isinstance(field_labels, dict):
        return normalized
    for raw_key, raw_label in field_labels.items():
        if not isinstance(raw_key, str) or not raw_key.strip():
            continue
        if not isinstance(raw_label, str) or not raw_label.strip():
            continue
        normalized[raw_key.strip()] = raw_label.strip()
    return normalized


def _merge_label_index_with_entry_labels(
    label_index: dict[str, str],
    field_labels: dict[str, str],
) -> dict[str, str]:
    """优先保留 schema 抽取结果，再用 field_labels 补齐缺失键。"""

    merged = dict(label_index)
    for key, value in _normalize_entry_field_labels(field_labels).items():
        merged.setdefault(key, value)
    return merged


def _collect_schema_field_labels(
    schema_node: dict[str, Any],
    label_index: dict[str, str],
    *,
    prefix: str,
) -> None:
    """递归抽取 schema 字段描述，并按路径写入索引。"""

    properties = schema_node.get("properties")
    if not isinstance(properties, dict):
        return

    for field_name, field_schema in properties.items():
        if not isinstance(field_schema, dict):
            continue
        field_path = f"{prefix}.{field_name}" if prefix else field_name
        label = extract_schema_description(field_schema)
        if label:
            label_index[field_path] = label
        _collect_nested_schema_labels(
            field_schema,
            label_index,
            field_path=field_path,
        )


def _collect_nested_schema_labels(
    field_schema: dict[str, Any],
    label_index: dict[str, str],
    *,
    field_path: str,
) -> None:
    """处理 object / array<object> 的子字段描述。"""

    field_type = str(field_schema.get("type") or "").strip().lower()
    if field_type == "object":
        _collect_schema_field_labels(field_schema, label_index, prefix=field_path)
        return
    if field_type != "array":
        return

    items = field_schema.get("items")
    if not isinstance(items, dict):
        return
    if str(items.get("type") or "").strip().lower() != "object":
        return
    _collect_schema_field_labels(items, label_index, prefix=f"{field_path}[]")


def _build_context_pool(
    entry: ApiCatalogEntry,
    execution_result: ApiQueryExecutionResult,
    *,
    step_id: str | None = None,
    extra_meta: dict[str, Any] | None = None,
) -> dict[str, ApiQueryContextStepResult]:
    """将单接口执行结果包装成 `context_pool` 结构。"""

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
    """生成稳定的步骤 ID。"""

    return f"step_{entry.id}"


def _build_error_detail(execution_result: ApiQueryExecutionResult) -> ApiQueryExecutionErrorDetail | None:
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
        `context_pool` 的任务是支撑解释和渲染，而不是替代完整数据翻页接口。这里统一裁剪到
        少量样本，兼顾可解释性与网关负载控制。

    Edge Cases:
        - 单对象保持对象形态，避免详情页被强行改写成单元素数组
        - 超过 `_CONTEXT_ROW_LIMIT` 时会补 `truncated_count`，方便前端和日志识别这是预览不是全量
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
    if execution_result.skipped_reason == "wait_select_required":
        return "命中多个候选值，请先选择后继续。"
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
    """在高危写意图场景下挂载快照凭证。

    功能：
        快照只服务高风险写意图审计，因此这里把是否采集的判断集中在响应出口，避免不同调用方
        各自决定是否留痕。

    Edge Cases:
        - 非高危意图不会生成快照，避免普通查询把快照存储打爆
        - 即使 ui_spec 为空，也仍允许 snapshot_service 自行决定是否记录最小审计信息
    """

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
        当前代码库里 `DynamicUIService` 仍处于新旧接口并存阶段。这里提供一层兼容包装，
        让响应构建器始终拿到统一的 `UISpecBuildResult`，避免调用方到处判断方法签名。

    Edge Cases:
        - 老版本 `generate_ui_spec_result/generate_ui_spec` 不支持 `trace_id` 时会自动回退旧签名
        - 旧接口只能返回裸 spec，因此 validation/frozen 会回退为空结果和 `False`
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
    """压缩第五阶段 Guard 错误，便于快速定位。"""

    if not validation.errors:
        return "[]"
    items = [f"{error.code}@{error.path}" for error in validation.errors[:5]]
    if len(validation.errors) > 5:
        items.append(f"...(+{len(validation.errors) - 5})")
    return "[" + ", ".join(items) + "]"


def _format_query_domains_for_response(query_domains: list[str]) -> list[str]:
    """把业务域列表标准化为对外响应形态。"""

    return [item for item in dict.fromkeys(query_domains) if item and item != "all"] or ["generic"]
