from __future__ import annotations

import logging
from typing import Any

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
    ApiQueryPatchContext,
    ApiQueryResponse,
    ApiQueryResponseMode,
    ApiQueryUIAction,
    ApiQueryUIRuntime,
)
from app.services.api_catalog.dag_executor import DagExecutionReport, DagStepExecutionRecord
from app.services.api_catalog.registry_source import ApiCatalogRegistrySource
from app.services.api_catalog.schema import ApiCatalogEntry
from app.services.api_query_state import ApiQueryExecutionState, ApiQueryRuntimeContext, ApiQueryState
from app.services.dynamic_ui_service import DynamicUIService, UISpecBuildResult
from app.services.ui_catalog_service import UICatalogService
from app.services.ui_snapshot_service import UISnapshotService
from app.services.ui_spec_guard import UISpecValidationResult
from app.services.api_catalog.business_intents import (
    NOOP_BUSINESS_INTENT,
    get_business_intent_catalog_service,
    normalize_business_intent_codes,
    resolve_business_intent_risk_level,
)

logger = logging.getLogger(__name__)

_QUERY_PARAM_SOURCE_BY_METHOD = {"GET": "queryParams", "POST": "body"}
_LIST_FILTER_EXCLUDED_FIELDS = {"id", "page", "pageNum", "pageSize", "size", "limit"}
# 这里固定保留 5 条是为了给 Renderer 足够上下文，又避免把大结果集整包塞进生成链路导致注意力失焦。
_CONTEXT_ROW_LIMIT = 5


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
        response_mode: ApiQueryResponseMode,
        patch_context: ApiQueryPatchContext | None,
    ) -> ApiQueryResponse:
        """把执行状态折叠为最终成功/部分成功/patch 响应。

        功能：
            当前路由阶段仍负责拿到执行报告，但“如何把执行事实压成前端契约”已经不应继续
            留在 HTTP 入口里。这一层会统一：

            1. 汇总主执行状态
            2. 选择响应锚点
            3. 生成或冻结 UI Spec
            4. 在必要时附加快照审计元数据
        """

        execution_report = DagExecutionReport(
            plan=execution_state["plan"],
            records_by_step_id=execution_state["records_by_step_id"],
            execution_order=execution_state["execution_order"],
        )
        context_pool = _build_plan_context_pool(execution_report)
        aggregate_status = _summarize_execution_report(execution_report)
        execution_state["aggregate_status"] = aggregate_status
        state["execution_status"] = aggregate_status

        anchor_record = _select_response_anchor(execution_report)
        internal_query_domains = _collect_execution_domains(execution_report, query_domains_hint)
        query_domains = _format_query_domains_for_response(internal_query_domains)
        business_intents = _build_business_intents(business_intent_codes)
        response_plan = _build_response_execution_plan(execution_report.plan, runtime_context.step_entries)
        state["plan"] = response_plan

        data_for_ui = _build_ui_data_from_execution_report(execution_report, anchor_record)
        runtime = _build_runtime_from_execution_report(
            execution_report,
            anchor_record,
            business_intents=business_intents,
            ui_catalog_service=self._ui_catalog_service,
        )

        if response_mode == ApiQueryResponseMode.PATCH:
            response = _build_patch_mode_response(
                trace_id=state["trace_id"],
                execution_report=execution_report,
                aggregate_status=aggregate_status,
                anchor_record=anchor_record,
                response_plan=response_plan,
                runtime=runtime,
                patch_context=patch_context,
            )
            state["ui_runtime"] = response.ui_runtime
            state["ui_spec"] = response.ui_spec
            state["response"] = response
            return response

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
                "query_render_mode": _infer_query_render_mode(execution_report, anchor_record),
                "context_pool": {step_id: step.model_dump(exclude_none=True) for step_id, step in context_pool.items()},
                "business_intents": [intent.model_dump() for intent in business_intents],
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
            "%s success mode=%s status=%s api_id=%s step_count=%s",
            runtime_context.log_prefix,
            state["request_mode"],
            aggregate_status,
            anchor_record.entry.id if anchor_record else None,
            len(execution_report.records_by_step_id),
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
        """把第二阶段失败折叠为冻结只读 Notice。"""

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
        """把第三阶段规划失败折叠为冻结只读 Notice。"""

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
        """

        query_domains = _format_query_domains_for_response(
            list(entry.domain and [entry.domain] or query_domains_hint)
        )
        business_intents = _build_business_intents([business_intent_code])

        # 从接口参数 Schema 与预填值构建表单字段列表
        form_fields = _build_mutation_form_fields(entry, pre_fill_params)

        # 构造带 form 的运行时契约
        form_code = f"{entry.id}_form"
        requested_component_codes = [
            "PlannerCard",
            "PlannerMetric",
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
                state_path="/form",
                fields=form_fields,
                submit=ApiQueryFormSubmitRuntime(
                    business_intent=business_intent_code,
                    confirm_required=True,
                ),
            ),
        )

        # 生成预填表单 UI Spec
        form_state = _build_prefilled_form_state(
            fields=form_fields,
            pre_fill_params=pre_fill_params,
        )
        ui_build_result = await _generate_ui_spec_result(
            self._dynamic_ui,
            intent="mutation_form",
            data=pre_fill_params,
            context={
                "title": f"确认修改：{entry.description}",
                "user_query": state.get("query_text", ""),
                "api_id": entry.id,
                "form_code": form_code,
                "business_intent": business_intent_code,
                "pre_fill_params": pre_fill_params,
                "form_fields": [f.model_dump(exclude_none=True) for f in form_fields],
                "form_state": form_state,
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
                    params=pre_fill_params,
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




def _build_business_intents(intent_codes: list[str]) -> list[ApiQueryBusinessIntent]:
    """将业务意图编码转换为对外响应对象。"""

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
) -> list[ApiQueryFormFieldRuntime]:
    """从 mutation 接口的 param_schema 与预填值构造表单字段运行时契约。

    设计意图：
        mutation form 快路不走第五阶段渲染器，因此参数 Schema 是构造表单字段
        定义的唯一来源。LLM 提取的预填值决定了该字段的初始 `state_path` 绑定
        和 `source_kind`（已填写 → context，未填写 → user_input）。

        主键/ID 字段（名称以 id/Id 结尾或以 Id 开头）会标记为 `writable=False`，
        让 `_infer_form_mode` 推导出 `edit`，符合"修改已知记录"的语义。
    """

    schema_properties = entry.param_schema.properties if entry.param_schema else {}
    required_fields = set(entry.param_schema.required) if entry.param_schema else set()

    focused_fields: list[ApiQueryFormFieldRuntime] = []
    fallback_fields: list[ApiQueryFormFieldRuntime] = []

    for field_name, prop in schema_properties.items():
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
        fallback_fields.append(field_runtime)

        # mutation form 的目标是“确认本次意图提取出来的变更参数”，不是把整份 OpenAPI
        # schema 原封不动摊成超长 CRUD 表单。这里优先保留三类字段：
        # 1. 本次查询已提取出值的字段（例如 id/email）
        # 2. 接口声明必填的字段
        # 3. 只读标识符字段（用于让用户明确当前修改的是哪条记录）
        if has_value or field_name in required_fields or is_identifier:
            focused_fields.append(field_runtime)

    if focused_fields:
        if not any(field.writable for field in focused_fields):
            # 只抽到标识符而没有任何可编辑字段时，确认页会退化成“只能看不能改”的空壳。
            # 这里补回 schema 里的可编辑字段，让前端至少能展示一份可填写表单。
            focused_fields.extend(
                field
                for field in fallback_fields
                if field.writable and field.submit_key not in {item.submit_key for item in focused_fields}
            )
        return focused_fields

    # 某些创建类 mutation 可能暂时没有从自然语言里提取出任何值。
    # 这时退回完整字段集合，避免把真正可提交的表单裁成空壳。
    return fallback_fields


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
    """根据目录参数 schema 推导列表筛选字段。"""

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
    """根据接口元数据和执行结果推导前端运行时契约。"""

    rows = _normalize_rows(execution_result.data)
    action_codes = {"refresh", "export"}
    requested_component_codes = ["PlannerCard", "PlannerTable", "PlannerDetailCard", "PlannerNotice"]
    if _has_write_business_intent(business_intents):
        requested_component_codes.extend(["PlannerForm", "PlannerInput", "PlannerSelect", "PlannerButton"])
    components = ui_catalog_service.get_component_codes(intent="query", requested_codes=requested_component_codes)
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
            pagination=ApiQueryListPaginationRuntime(
                enabled=pagination_enabled,
                total=execution_result.total,
                page_size=_infer_page_size(params, len(rows)),
                current_page=_infer_current_page(params),
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
    """从最终 Spec 中提取表单运行时契约。"""

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
        # generated spec 只能声明 `api_id`；真正可执行的提交地址要回到统一配置模板，
        # 这样不同环境、灰度域名和回滚切换都不会散落到 renderer 契约里。
        route_url=_build_runtime_invoke_url(api_id),
        ui_action="remoteMutation",
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
                    "option_source": _extract_form_option_source(props.get("options")),
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


def _extract_form_option_source(options_payload: Any) -> ApiQueryFormOptionSourceRuntime | None:
    """从 `PlannerSelect.props.options` 推导可复用的选项来源契约。"""

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


def _write_state_value(state: dict[str, Any], state_path: str, value: Any) -> None:
    """按 `/form/email` 形式把值写入嵌套 state。"""

    if not isinstance(state, dict) or not state_path.startswith("/"):
        return

    current: dict[str, Any] = state
    segments = [item for item in state_path.split("/") if item]
    if not segments:
        return

    for segment in segments[:-1]:
        child = current.get(segment)
        if not isinstance(child, dict):
            child = {}
            current[segment] = child
        current = child
    current[segments[-1]] = value


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
        _write_state_value(
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


def _infer_current_page(params: dict[str, Any]) -> int | None:
    """从查询参数中推断当前页码。"""

    for key in ("page", "pageNum", "page_no", "pageIndex", "current"):
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
) -> list[dict[str, Any]]:
    """为当前规则渲染器构造可展示的数据集。"""

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


def _build_runtime_from_execution_report(
    execution_report: DagExecutionReport,
    anchor_record: DagStepExecutionRecord | None,
    *,
    business_intents: list[ApiQueryBusinessIntent],
    ui_catalog_service: UICatalogService,
) -> ApiQueryUIRuntime:
    """根据执行报告推导前端运行时契约。"""

    if len(execution_report.records_by_step_id) == 1 and anchor_record is not None:
        return _build_ui_runtime(
            anchor_record.entry,
            anchor_record.execution_result,
            params=anchor_record.resolved_params,
            business_intents=business_intents,
            ui_catalog_service=ui_catalog_service,
        )
    return ApiQueryUIRuntime(
        components=ui_catalog_service.get_component_codes(
            intent="query",
            requested_codes=["PlannerCard", "PlannerTable", "PlannerNotice"],
        ),
        ui_actions=_build_runtime_actions({"refresh", "export"}, ui_catalog_service=ui_catalog_service),
    )


def _infer_query_render_mode(
    execution_report: DagExecutionReport,
    anchor_record: DagStepExecutionRecord | None,
) -> str:
    """推断当前查询结果应使用的读态渲染模式。"""

    if len(execution_report.records_by_step_id) > 1:
        return "summary_table"
    if anchor_record is None:
        return "table"
    if isinstance(anchor_record.execution_result.data, dict):
        return "detail"
    return "table"


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
    """构造列表二跳的 patch 响应。"""

    requested_target = patch_context.mutation_target if patch_context is not None else None
    ui_spec = _build_list_patch_spec(
        anchor_record=anchor_record,
        runtime=runtime,
        aggregate_status=aggregate_status,
        requested_target=requested_target,
    )
    return ApiQueryResponse(
        trace_id=trace_id,
        execution_status=aggregate_status,
        execution_plan=response_plan,
        ui_runtime=runtime,
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
    """把单步列表结果压缩成前端可直接应用的 patch spec。"""

    mutation_target = runtime.list.pagination.mutation_target or requested_target or "report-table.props.dataSource"
    rows: list[dict[str, Any]] = []
    if aggregate_status in {ApiQueryExecutionStatus.SUCCESS, ApiQueryExecutionStatus.EMPTY} and anchor_record is not None:
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
    """构造单条 replace patch。"""

    return {"op": "replace", "path": path, "value": value}


def _infer_patch_pagination_container_path(mutation_target: str) -> str | None:
    """从 `dataSource` 目标路径反推分页状态容器路径。"""

    if not mutation_target:
        return None
    if mutation_target.endswith(".dataSource"):
        return mutation_target[: -len(".dataSource")] + ".pagination"
    return None


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
    """裁剪进入 `context_pool` 和 Renderer 的数据体量。"""

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
    """兼容第五阶段新旧接口，统一返回带 Guard 状态的结果对象。"""

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
