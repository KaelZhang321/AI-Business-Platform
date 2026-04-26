from __future__ import annotations

from copy import deepcopy
import json
import logging
import re
from dataclasses import dataclass, field as dataclass_field
from statistics import mean
from typing import Any

from app.core.config import settings
from app.models.schemas import (
    ApiQueryExecutionStatus,
    ApiQueryFormFieldRuntime,
    ApiQueryListFilterFieldRuntime,
    ApiQueryUIRuntime,
    KnowledgeResult,
)
from app.services.api_query_request_schema_gate import build_request_schema_gated_fields
from app.services.ui_catalog_service import UICatalogService
from app.services.ui_spec_guard import UISpecGuard, UISpecValidationResult
from app.utils.json_utils import extract_first_json_object_text, load_json_object
from app.utils.state_path_utils import read_state_value, write_state_value

logger = logging.getLogger(__name__)

_LLM_RENDER_ROW_LIMIT = 3
_LLM_RENDER_KEY_LIMIT = 8
_LLM_RENDER_STRING_LIMIT = 200
_LLM_RENDER_MAX_ATTEMPTS = 2


@dataclass(slots=True)
class UISpecBuildResult:
    """第五阶段 UI Spec 构建结果。

    功能：
        把“渲染成功但需冻结”和“完全未产出 Spec”明确区分开，避免调用方继续依赖
        `None` 或异常去猜测当前处于哪一种失败模式。

    Args:
        spec: 最终应返回给前端的 Spec。冻结场景下会是网关构造的安全兜底视图。
        validation: Guard 校验结果；无 Spec 场景下通常为空结果。
        frozen: 是否触发了“冻结当前操作视图”的硬失败策略。
    """

    spec: dict[str, Any] | None = None
    validation: UISpecValidationResult = dataclass_field(default_factory=UISpecValidationResult)
    frozen: bool = False


class DynamicUIService:
    """根据意图构建 json-render 兼容的 UI Spec。

    支持两种模式：
    - 规则模式（默认）：基于硬编码模板，根据数据特征自动生成 UI Spec
    - LLM 模式（实验性）：通过 LLM 生成 UI Spec，需设置 LLM_UI_SPEC_ENABLED=true
    """

    def __init__(
        self,
        catalog_service: UICatalogService | None = None,
        guard: UISpecGuard | None = None,
        llm_service: Any | None = None,
    ) -> None:
        """初始化动态渲染服务。

        功能：
            第五阶段 Prompt 的组件目录已经不应该再散落在各个模块里。
            这里注入 `UICatalogService`，让规则渲染和 LLM 渲染都消费同一份目录快照。

        Args:
            catalog_service: 可选的 UI 目录服务。测试可注入替身，生产默认懒加载单例。
            llm_service: 可选的 LLM 服务。`api_query` 会注入 Ark 专用实现，其他链路仍可沿用默认值。
        """
        self._catalog_service = catalog_service
        self._guard = guard
        self._llm_service = llm_service

    async def generate_ui_spec(
        self,
        intent: str,
        data: Any,
        context: dict | None = None,
        *,
        status: ApiQueryExecutionStatus | str | None = None,
        runtime: ApiQueryUIRuntime | None = None,
        trace_id: str | None = None,
    ) -> dict[str, Any] | None:
        """按执行状态和数据形状生成 json-render 规范。

        功能：
            将 `api_query` 的执行状态机翻译为可渲染的 UI 结果，避免前端直接暴露
            上游报错、空结果或网关跳过执行等底层细节。

        Args:
            intent: 当前 UI 生成意图，例如 `query`、`knowledge`。
            data: 已经过网关裁剪后的渲染数据。
            context: 渲染上下文，至少可包含 `user_query`、`context_pool`、提示文案等。
            status: 当前主步骤的执行状态。
            runtime: 当前查询可用的前端运行时能力定义。

        Returns:
            合法的 json-render Spec；若当前场景不适合生成 UI，则返回 `None`。

        Edge Cases:
            - `ERROR` / `EMPTY` / `SKIPPED` 优先返回 Notice，防止前端误渲染半成品表格
            - `PARTIAL_SUCCESS` 会在正常内容上叠加风险提示，而不是直接吞掉成功数据
            - 旧版规则渲染器仍会先产出树形节点，本方法负责在出口统一折叠为
              `root/state/elements`，避免 route 层同时兼容两套 Spec 契约
        """
        result = await self.generate_ui_spec_result(
            intent,
            data,
            context,
            status=status,
            runtime=runtime,
            trace_id=trace_id,
        )
        return result.spec

    async def generate_ui_spec_result(
        self,
        intent: str,
        data: Any,
        context: dict | None = None,
        *,
        status: ApiQueryExecutionStatus | str | None = None,
        runtime: ApiQueryUIRuntime | None = None,
        trace_id: str | None = None,
    ) -> UISpecBuildResult:
        """生成并校验第五阶段 UI Spec。

        功能：
            渲染器的职责不再只是“产出一个页面描述”，还要承担写链路的最后一道安全闸。
            因此这里统一执行：

            1. 生成候选 Spec
            2. 归一化为 flat spec
            3. 交给 `UISpecGuard` 做结构和绑定校验
            4. 一旦失败，冻结为不可交互的安全提示视图

        Args:
            intent: 当前渲染意图。
            data: 已经裁剪过的主数据载荷。
            context: 渲染上下文，供标题、提示语和 `context_pool` 使用。
            status: 当前执行状态。
            runtime: 当前请求允许暴露的前端运行时契约。
            trace_id: 当前请求链路追踪 ID，用于结构化失败日志。

        Returns:
            `UISpecBuildResult`。调用方可依据 `frozen` 决定是否继续暴露交互能力。

        Edge Cases:
            - 无数据且无需展示 Notice 时，返回 `spec=None`
            - Guard 失败时绝不透传半成品 Spec，而是统一冻结为只读提示视图
            - 冻结视图不依赖 LLM，确保在渲染链路失真时依旧可稳定返回
        """
        candidate_spec = await self._build_candidate_spec(
            intent,
            data,
            context,
            status=status,
            runtime=runtime,
            trace_id=trace_id,
        )
        if candidate_spec is None:
            return UISpecBuildResult()

        candidate_spec = self._sanitize_runtime_request_metadata(
            candidate_spec,
            intent=intent,
            context=context,
            runtime=runtime,
        )

        validation = self._get_guard().validate(candidate_spec, intent=intent, runtime=runtime)
        if validation.is_valid:
            return UISpecBuildResult(spec=candidate_spec, validation=validation, frozen=False)

        logger.warning(
            "UI Spec guard rejected output trace_id=%s intent=%s errors=%s spec_summary=%s",
            trace_id or "-",
            intent,
            self._format_validation_errors(validation),
            self._summarize_payload(candidate_spec),
        )
        return UISpecBuildResult(
            spec=self._frozen_spec(context),
            validation=validation,
            frozen=True,
        )

    def _sanitize_runtime_request_metadata(
        self,
        spec: dict[str, Any],
        *,
        intent: str,
        context: dict[str, Any] | None,
        runtime: ApiQueryUIRuntime | None,
    ) -> dict[str, Any]:
        """在 Guard 校验前统一回写稳定的 runtime 请求元数据。

        功能：
            LLM 生成的详情卡片和动作对象可能会把展示 label 混进 `body/queryParams`，
            导致请求键名漂移。这里基于 runtime 契约重新回写已知节点的请求元数据，
            保证前端真正执行时只看到 request_schema 允许的键。

        Args:
            spec: 候选 UI Spec（通常来自规则渲染或 LLM 渲染）。
            intent: 当前渲染意图（query / mutation_form / knowledge 等）。
            context: 响应层透传的渲染上下文。
            runtime: 当前请求可暴露的运行时契约。

        Returns:
            已标准化 runtime 元数据的 Spec；若不满足处理条件则原样返回。

        Edge Cases:
            - runtime 缺失或 spec 非 flat：跳过改写，避免误污染旧结构
            - `elements` 非字典：直接返回原 Spec，交给 Guard 统一兜底
        """

        if runtime is None or not self._is_flat_spec(spec):
            return spec

        sanitized_spec = deepcopy(spec)
        elements = sanitized_spec.get("elements")
        if not isinstance(elements, dict):
            return spec

        normalized_context = context if isinstance(context, dict) else {}
        state = sanitized_spec.get("state")
        normalized_state = state if isinstance(state, dict) else {}

        if intent == "query":
            self._sanitize_query_runtime_metadata(
                elements=elements,
                state=normalized_state,
                context=normalized_context,
                runtime=runtime,
            )
        elif intent == "mutation_form":
            self._sanitize_mutation_runtime_metadata(
                elements=elements,
                context=normalized_context,
                runtime=runtime,
            )
        return sanitized_spec

    def _sanitize_query_runtime_metadata(
        self,
        *,
        elements: dict[str, Any],
        state: dict[str, Any],
        context: dict[str, Any],
        runtime: ApiQueryUIRuntime,
    ) -> None:
        """修正查询页中列表、详情和行级动作的请求元数据。

        功能：
            query 页面同时存在列表、筛选、详情和分页等多个交互入口。
            这里统一把这些节点的请求参数回写到 runtime 契约，避免前端在不同入口
            读到不一致的 `api/queryParams/body`，导致同一查询链路出现行为分叉。

        Args:
            elements: flat spec 的 `elements` 映射。
            state: flat spec 的 `state`，用于回填详情标识值。
            context: 渲染上下文，包含 flow_num/created_by/request_params 等事实字段。
            runtime: query 运行时契约。

        Returns:
            无返回值，原地更新 `elements` 中相关节点的请求元数据。

        Edge Cases:
            - list 未启用：只尝试详情节点修正
            - detail 未启用或缺少 identifier：直接跳过详情回填，避免生成无效请求
            - row_actions 来自上游 `context.row_actions` 时，优先保留上游显式动作定义
        """

        if runtime.list.enabled:
            # 1. 先构造三类稳定参数模板：列表基线、筛选提交、筛选重置。
            # 这样做是为了保证同页不同按钮读取的是同一份 runtime 口径。
            list_request_fields = _build_runtime_request_fields(
                runtime.list.api_id,
                param_source=runtime.list.param_source,
                params=dict(runtime.list.query_context.current_params),
                flow_num=context.get("flow_num"),
                created_by=context.get("created_by"),
                request_schema_fields=runtime.list.request_schema_fields,
            )
            detail_runtime_strategy_fields = self._build_detail_runtime_strategy_fields(runtime)
            filter_fields = list(runtime.list.filters.fields)
            filter_submit_request_fields = _build_runtime_request_fields(
                runtime.list.api_id,
                param_source=runtime.list.param_source,
                params=_build_filter_submit_params(runtime, filter_fields),
                flow_num=context.get("flow_num"),
                created_by=context.get("created_by"),
                request_schema_fields=runtime.list.request_schema_fields,
            )
            filter_reset_request_fields = _build_runtime_request_fields(
                runtime.list.api_id,
                param_source=runtime.list.param_source,
                params=_build_filter_reset_params(runtime, filter_fields),
                flow_num=context.get("flow_num"),
                created_by=context.get("created_by"),
                request_schema_fields=runtime.list.request_schema_fields,
            )

            # 2. 再按组件类型批量覆写，确保 Table/Pagination/Button 一致消费同一契约。
            for element in elements.values():
                if not isinstance(element, dict):
                    continue
                props = element.get("props")
                if not isinstance(props, dict):
                    continue
                element_type = element.get("type")
                if element_type == "PlannerForm" and props.get("formCode") == "query_filters":
                    props.update(list_request_fields)
                elif element_type == "PlannerTable":
                    props.update(list_request_fields)
                    context_row_actions = context.get("row_actions")
                    if isinstance(context_row_actions, list) and context_row_actions:
                        props["rowActions"] = self._normalize_row_actions(context_row_actions)
                    elif runtime.detail.enabled and runtime.detail.api_id:
                        props["rowActions"] = [
                            {
                                "action": runtime.detail.ui_action or "remoteQuery",
                                "label": "查看详情",
                                "params": {
                                    "api_id": runtime.detail.api_id,
                                    **detail_runtime_strategy_fields,
                                    **_build_runtime_request_fields(
                                        runtime.detail.api_id,
                                        param_source=runtime.detail.request.param_source,
                                        params={
                                            (
                                                runtime.detail.request.identifier_param
                                                or runtime.detail.source.identifier_field
                                            ): {"$bindRow": runtime.detail.source.identifier_field}
                                        },
                                        flow_num=context.get("flow_num"),
                                        created_by=context.get("created_by"),
                                        request_schema_fields=(
                                            runtime.detail.request.request_schema_fields
                                            or [runtime.detail.request.identifier_param]
                                        ),
                                    ),
                                },
                            }
                        ]
                elif element_type == "PlannerPagination":
                    props.update(
                        {
                            "enabled": runtime.list.pagination.enabled,
                            "total": runtime.list.pagination.total,
                            "currentPage": runtime.list.pagination.current_page,
                            "pageSize": runtime.list.pagination.page_size,
                            "pageParam": runtime.list.pagination.page_param,
                            "pageSizeParam": runtime.list.pagination.page_size_param,
                            **list_request_fields,
                        }
                    )
                elif element_type == "PlannerButton":
                    # 查询/重置按钮必须走固定动作覆盖，避免 LLM 把 label 改写后参数失真。
                    label = props.get("label")
                    if label == "查询":
                        self._overwrite_button_action_params(
                            element=element,
                            expected_action=runtime.list.ui_action or "remoteQuery",
                            api_id=runtime.list.api_id,
                            request_fields=filter_submit_request_fields,
                        )
                    elif label == "重置":
                        self._overwrite_button_action_params(
                            element=element,
                            expected_action=runtime.list.ui_action or "remoteQuery",
                            api_id=runtime.list.api_id,
                            request_fields=filter_reset_request_fields,
                        )

        if not runtime.detail.enabled or not runtime.detail.api_id:
            return

        # 3. 详情卡入口单独处理：先定位主键值，再按 detail request_schema 回写请求。
        detail_identifier_param = runtime.detail.request.identifier_param or runtime.detail.source.identifier_field
        if not isinstance(detail_identifier_param, str) or not detail_identifier_param:
            return
        detail_identifier_value = self._resolve_detail_identifier_value(
            elements=elements,
            context=context,
            state=state,
            runtime=runtime,
        )
        detail_request_fields = _build_runtime_request_fields(
            runtime.detail.api_id,
            param_source=runtime.detail.request.param_source,
            params={detail_identifier_param: detail_identifier_value} if detail_identifier_value is not None else {},
            flow_num=context.get("flow_num"),
            created_by=context.get("created_by"),
            request_schema_fields=runtime.detail.request.request_schema_fields or [detail_identifier_param],
        )
        for element in elements.values():
            if not isinstance(element, dict) or element.get("type") != "PlannerDetailCard":
                continue
            props = element.get("props")
            if isinstance(props, dict):
                props.update(detail_request_fields)

    def _sanitize_mutation_runtime_metadata(
        self,
        *,
        elements: dict[str, Any],
        context: dict[str, Any],
        runtime: ApiQueryUIRuntime,
    ) -> None:
        """修正 mutation 表单页的表单和提交按钮请求元数据。

        功能：
            mutation 页面属于“高风险确认后写入”路径，提交参数必须完全受 runtime 契约约束。
            这里统一把表单容器和提交按钮的动作参数回写到同一请求模板，避免前端从不同
            节点读取时出现键名漂移或字段缺失。

        Args:
            elements: flat spec 的 `elements` 映射。
            context: 渲染上下文，含 submit_payload/flow_num/created_by 等事实字段。
            runtime: mutation form 运行时契约。

        Returns:
            无返回值，原地更新相关节点元数据。

        Edge Cases:
            - form 未启用或 api_id 缺失：直接跳过，防止暴露不可提交的假写入口
            - submit_payload 缺失：回退字段级 `$bindState` 模板保证“用户最终输入”可提交
        """

        if not runtime.form.enabled or not runtime.form.api_id:
            return

        submit_payload = self._resolve_mutation_submit_payload(context=context, runtime=runtime)
        request_fields = _build_runtime_request_fields(
            runtime.form.api_id,
            param_source="body",
            params=submit_payload,
            flow_num=context.get("flow_num"),
            created_by=context.get("created_by"),
            request_schema_fields=runtime.form.request_schema_fields
            or [field.submit_key for field in runtime.form.fields],
        )
        for element in elements.values():
            if not isinstance(element, dict):
                continue
            props = element.get("props")
            if element.get("type") == "PlannerForm" and isinstance(props, dict):
                if runtime.form.form_code:
                    props["formCode"] = runtime.form.form_code
                props.update(request_fields)
                continue
            if element.get("type") == "PlannerButton":
                self._overwrite_button_action_params(
                    element=element,
                    expected_action=runtime.form.ui_action or "remoteMutation",
                    api_id=runtime.form.api_id,
                    request_fields=request_fields,
                )

    @staticmethod
    def _overwrite_button_action_params(
        *,
        element: dict[str, Any],
        expected_action: str,
        api_id: str | None,
        request_fields: dict[str, Any],
    ) -> None:
        """按给定 runtime 契约覆写按钮动作参数。"""

        on = element.get("on")
        if not isinstance(on, dict):
            return
        press = on.get("press")
        if not isinstance(press, dict):
            return
        action = press.get("action")
        if action != expected_action:
            return
        press["params"] = {
            "api_id": api_id,
            **request_fields,
        }

    def _resolve_detail_identifier_value(
        self,
        *,
        elements: dict[str, Any],
        context: dict[str, Any],
        state: dict[str, Any],
        runtime: ApiQueryUIRuntime,
    ) -> Any:
        """恢复详情请求的主键值，优先选择稳定来源而非展示文案。

        功能：
            详情请求是否正确命中，核心取决于 identifier 值是否稳定。由于 UI 可能被 LLM
            重新组织，不能只依赖某个固定字段位置，这里按“契约优先 -> 状态回填 -> 展示兜底”
            顺序分层恢复，最大化命中率。

        Args:
            elements: 当前 flat spec 元素映射。
            context: 渲染上下文（含 request_params/form_state）。
            state: 当前页面 state。
            runtime: 详情运行时契约。

        Returns:
            恢复出的 identifier 值；无法恢复时返回 `None`。

        Edge Cases:
            - request_params 缺失：自动回退 form_state 和 detail card 扫描
            - label 被中文 description 替换：同时匹配字段名与展示名
            - 所有来源都为空：返回 None，避免发送错误主键
        """

        # 1. 首选 request_params：这是响应层传下来的原始请求事实，优先级最高。
        request_params = context.get("request_params")
        if isinstance(request_params, dict):
            identifier_param = runtime.detail.request.identifier_param
            if isinstance(identifier_param, str) and identifier_param in request_params:
                return request_params.get(identifier_param)
            source_identifier_field = runtime.detail.source.identifier_field
            if isinstance(source_identifier_field, str) and source_identifier_field in request_params:
                return request_params.get(source_identifier_field)

        # 2. 次选 form_state：兼容用户在页面内改写后回查详情的场景。
        root_state = context.get("form_state")
        if isinstance(root_state, dict):
            identifier_param = runtime.detail.request.identifier_param
            if isinstance(identifier_param, str):
                state_value = read_state_value(root_state, f"/form/{identifier_param}")
                if state_value is not None:
                    return state_value

        source_identifier_field = runtime.detail.source.identifier_field
        if isinstance(source_identifier_field, str):
            # 详情卡 label 可能已被 schema description/title 替换；
            # 主键回填时需同时兼容“原始字段名”和“展示字段名”两条匹配路径。
            label_index = self._build_response_field_label_index(context)
            identifier_labels = {
                source_identifier_field,
                self._resolve_field_label(
                    field_name=source_identifier_field,
                    label_index=label_index,
                    field_path=source_identifier_field,
                ),
            }
            for element in elements.values():
                if not isinstance(element, dict) or element.get("type") != "PlannerDetailCard":
                    continue
                props = element.get("props")
                if not isinstance(props, dict):
                    continue
                items = props.get("items")
                if not isinstance(items, list):
                    continue
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    if item.get("label") in identifier_labels:
                        return item.get("value")

        # 3. 最后兜底页面 state，保证在上下文缺失时仍尽力恢复主键。
        identifier_param = runtime.detail.request.identifier_param
        if isinstance(identifier_param, str):
            state_value = read_state_value(state, f"/form/{identifier_param}")
            if state_value is not None:
                return state_value
        return None

    @staticmethod
    def _resolve_mutation_submit_payload(
        *,
        context: dict[str, Any],
        runtime: ApiQueryUIRuntime,
    ) -> dict[str, Any]:
        """解析 mutation 表单提交模板。

        功能：
            mutation 页面既要支持通用字段绑定，也要支持删除确认等“自定义 payload”场景。
            这里统一处理优先级：先尊重上下文显式模板，再回退字段绑定模板。

        Args:
            context: 渲染上下文，可能携带 `submit_payload` 覆盖模板。
            runtime: mutation form 运行时契约。

        Returns:
            提交 payload 模板（可包含 `$bindState` 占位符）。

        Edge Cases:
            - submit_payload 非字典：回退字段绑定模板，避免前端拿到不可执行参数
        """

        custom_submit_payload = context.get("submit_payload")
        if isinstance(custom_submit_payload, dict):
            return custom_submit_payload
        return {
            field.submit_key: {"$bindState": field.state_path}
            for field in runtime.form.fields
        }

    def _get_llm_service(self):
        """懒加载 LLMService 单例，避免规则模式也承担额外初始化成本。"""
        if not hasattr(self, "_llm_service") or self._llm_service is None:
            from app.services.llm_service import LLMService

            self._llm_service = LLMService()
        return self._llm_service

    def _get_catalog_service(self) -> UICatalogService:
        """懒加载 UI 目录服务。

        功能：
            `DynamicUIService` 既被 `api_query` 主链路复用，也会在测试中独立实例化。
            这里用懒加载兜住默认依赖，避免为了目录服务把所有调用点都改成显式注入。
        """
        if self._catalog_service is None:
            self._catalog_service = UICatalogService()
        return self._catalog_service

    def _get_guard(self) -> UISpecGuard:
        """懒加载 UI Spec Guard。

        功能：
            Guard 与目录服务必须消费同一份组件/动作快照，才能把“未注册”和“未启用”
            清晰区分开来。因此默认与 `UICatalogService` 共享依赖，而不是各自独立初始化。
        """
        if self._guard is None:
            self._guard = UISpecGuard(catalog_service=self._get_catalog_service())
        return self._guard

    async def _build_candidate_spec(
        self,
        intent: str,
        data: Any,
        context: dict | None,
        *,
        status: ApiQueryExecutionStatus | str | None,
        runtime: ApiQueryUIRuntime | None,
        trace_id: str | None,
    ) -> dict[str, Any] | None:
        """生成待 Guard 校验的候选 Spec。

        功能：
            Guard 只负责验证结构合法性，不负责决定“当前该渲染什么”。这里先按执行状态、
            渲染意图和数据形态挑选候选 Spec，再交给 Guard 做最后安全兜底。

        Edge Cases:
            - mutation_form 必须优先于通用 `SKIPPED -> Notice` 规则，否则确认页会被误短路
            - 没有主数据时返回 `None`，让上层明确感知“无需渲染”，而不是造空壳页面
            - LLM 渲染失败会自动回退规则模式，不影响主链可用性
        """
        execution_status = ApiQueryExecutionStatus(status) if status else None

        if intent == "mutation_form":
            mutation_spec = self._mutation_form_spec(context=context, runtime=runtime)
            if mutation_spec is not None:
                return mutation_spec

        if execution_status == ApiQueryExecutionStatus.ERROR:
            return self._notice_spec(
                title=(context or {}).get("title", "查询失败"),
                message=(context or {}).get("error", "业务接口调用失败"),
                tone="info",
            )
        if execution_status == ApiQueryExecutionStatus.EMPTY:
            return self._notice_spec(
                title=(context or {}).get("title", "暂无数据"),
                message=(context or {}).get("empty_message", "未查到符合条件的数据"),
                tone="info",
            )
        if execution_status == ApiQueryExecutionStatus.SKIPPED:
            return self._notice_spec(
                title=(context or {}).get("title", "查询已跳过"),
                message=(context or {}).get("skip_message", "由于缺少必要条件，当前查询未被执行。"),
                tone="info",
            )
        if not data:
            return None

        # 规则模式是当前生产兜底，LLM 只是在满足开关时尝试提升展示质量。
        if settings.llm_ui_spec_enabled:
            try:
                spec = await self._llm_generate_spec(intent, data, context, runtime, trace_id=trace_id)
                if spec:
                    normalized_spec = self._normalize_spec_shape(spec)
                    if normalized_spec:
                        return normalized_spec
            except Exception as exc:
                logger.warning(
                    "LLM UI Spec 生成失败，回退规则模式 trace_id=%s intent=%s error=%s",
                    trace_id or "-",
                    intent,
                    exc,
                )

        # 规则模式（默认）
        if intent == "knowledge" and isinstance(data, list):
            return self._normalize_spec_shape(self._knowledge_spec(data, context))

        if intent == "query" and isinstance(data, list) and data and isinstance(data[0], dict):
            return self._query_spec(
                data,
                context,
                runtime,
                include_partial_notice=execution_status == ApiQueryExecutionStatus.PARTIAL_SUCCESS,
            )

        if intent == "task" and isinstance(data, list):
            return self._normalize_spec_shape(self._task_spec(data))

        return None

    def _mutation_form_spec(
        self,
        *,
        context: dict[str, Any] | None,
        runtime: ApiQueryUIRuntime | None,
    ) -> dict[str, Any] | None:
        """构造 mutation confirm 场景的规则表单 Spec。

        功能：
            mutation form 虽然对外状态是 `SKIPPED`，但语义并不是“查询失败/跳过”，
            而是“AI 已识别出一条写操作，请用户确认后再提交”。因此这里必须绕过
            通用 `SKIPPED -> PlannerNotice` 规则，显式产出 `PlannerForm`。

        Args:
            context: 来自 `ApiQueryResponseBuilder.build_mutation_form_response()` 的渲染上下文。
            runtime: 当前 mutation form 的运行时契约。

        Returns:
            合法的 flat form spec；当运行时缺少表单契约时返回 `None`，交回上层兜底。

        Edge Cases:
            - `runtime.form` 未启用或缺少 `api_id` 时，必须返回 `None`，避免生成一个前端可见但无法提交的假表单
            - `context.submit_payload` 缺失时，回退到基于 `$bindState` 的延迟取值模板，保证用户修改后的最新输入能进入最终 `body`
            - runtime 元数据会同时挂到表单容器和提交按钮，兼容前端从“表单级上下文”或“动作级参数”两种入口取值
        """

        # 1. mutation confirm 是“可确认后提交”的业务页；如果运行时契约本身不完整，
        # 就不要向前端暴露半成品表单，交给上层退回安全兜底视图。
        if runtime is None or not runtime.form.enabled or not runtime.form.api_id:
            return None

        form_fields = list(runtime.form.fields)
        if not form_fields:
            return None

        # 2. 先补全完整 state，再决定展示字段。这样做的目的不是美观，而是确保
        # Guard 校验 `$bindState` 时每条路径都真实存在，提交按钮也能稳定复用同一份状态树。
        initial_state = self._build_mutation_form_state(
            fields=form_fields,
            form_state=(context or {}).get("form_state"),
        )
        visible_fields = self._select_visible_mutation_form_fields(form_fields, initial_state)
        if not visible_fields:
            visible_fields = form_fields

        elements: dict[str, Any] = {
            "root": {
                "type": "PlannerCard",
                "props": {
                    "title": (context or {}).get("title", "确认提交"),
                    "subtitle": (context or {}).get("subtitle", "请确认本次变更后再提交"),
                },
                "children": ["form"],
            },
            "form": {
                "type": "PlannerForm",
                "props": {
                    "formCode": runtime.form.form_code or "mutation_form",
                },
                "children": [],
            },
        }

        default_submit_payload: dict[str, Any] = {}
        for index, field in enumerate(visible_fields, start=1):
            element_id = f"form_field_{index}"
            elements["form"]["children"].append(element_id)
            elements[element_id] = self._build_mutation_field_element(field=field, state=initial_state)
            # 默认提交模板使用 `$bindState`，是为了让最终请求读取“用户确认后的当前值”，
            # 而不是把服务端首屏预填值写死在 action params 中。
            default_submit_payload[field.submit_key] = {"$bindState": field.state_path}

        custom_submit_payload = (context or {}).get("submit_payload")
        # 删除确认等特殊写场景会覆盖 submit_payload；普通 mutation confirm 继续走
        # 字段级绑定模板，保证所有可编辑字段天然参与提交。
        submit_payload = custom_submit_payload if isinstance(custom_submit_payload, dict) else default_submit_payload
        submit_request_fields = _build_runtime_request_fields(
            runtime.form.api_id,
            param_source="body",
            params=submit_payload,
            flow_num=(context or {}).get("flow_num"),
            created_by=(context or {}).get("created_by"),
            request_schema_fields=runtime.form.request_schema_fields,
        )

        submit_element_id = "form_submit"
        elements["form"]["children"].append(submit_element_id)
        # 表单容器和按钮同时携带 runtime 元数据，是为了兼容两类前端实现：
        # 一类从表单节点读取提交上下文，另一类只消费按钮 action params。
        elements["form"]["props"].update(
            _build_runtime_request_fields(
                runtime.form.api_id,
                param_source="body",
                params=submit_payload,
                flow_num=(context or {}).get("flow_num"),
                created_by=(context or {}).get("created_by"),
                request_schema_fields=runtime.form.request_schema_fields,
            )
        )
        elements[submit_element_id] = {
            "type": "PlannerButton",
            "props": {
                # 文案优先尊重上游上下文覆盖，其次才根据 confirm_required 区分“确认提交”和普通“提交”，
                # 这样删除/审核等高风险动作可以复用同一套表单结构但给出更准确的用户提示。
                "label": (
                    (context or {}).get("submit_label")
                    if isinstance((context or {}).get("submit_label"), str) and (context or {}).get("submit_label")
                    else ("确认提交" if runtime.form.submit.confirm_required else "提交")
                ),
            },
            "on": {
                "press": {
                    "action": runtime.form.ui_action or "remoteMutation",
                    "params": {
                        "api_id": runtime.form.api_id,
                        **submit_request_fields,
                    },
                }
            },
        }

        return {
            "root": "root",
            "state": initial_state,
            "elements": elements,
        }

    def _build_mutation_form_state(
        self,
        *,
        fields: list[ApiQueryFormFieldRuntime],
        form_state: Any,
    ) -> dict[str, Any]:
        """根据字段绑定路径构造完整表单 state。

        功能：
            Guard 会校验每一条 `$bindState` 路径是否真实存在，因此 mutation form 不能
            只把有值字段塞进 state。这里会按 `runtime.form.fields` 补全整棵 `/form` 状态树，
            保证按钮请求元数据和输入组件都能稳定绑定。
        """

        state: dict[str, Any] = {}
        incoming_state = form_state if isinstance(form_state, dict) else {}
        for field in fields:
            incoming_value = read_state_value(incoming_state, field.state_path)
            write_state_value(state, field.state_path, incoming_value)
        return state

    def _select_visible_mutation_form_fields(
        self,
        fields: list[ApiQueryFormFieldRuntime],
        state: dict[str, Any],
    ) -> list[ApiQueryFormFieldRuntime]:
        """筛选 mutation confirm 页面真正需要展示的字段。

        功能：
            mutation confirm 现阶段已经明确改成“按 request_schema 全量展示”，因此真正
            的裁剪责任前移到 response builder：只过滤系统维护字段（创建/更新/删除时间）。
            这里不再根据“是否有值/是否必填”做二次收缩，避免后端运行时契约与最终 UI
            产生字段不一致。
        """
        del state
        return list(fields)

    def _build_mutation_field_element(
        self,
        *,
        field: ApiQueryFormFieldRuntime,
        state: dict[str, Any],
    ) -> dict[str, Any]:
        """将单个 mutation 字段折叠为对应的 json-render 元素。

        功能：
            mutation confirm 的字段组件类型必须和运行时契约严格对齐，避免前端看到的控件形态
            与最终提交 `body/queryParams` 语义不一致。

        Edge Cases:
            - 不可写字段统一降为 `PlannerMetric`，防止用户误以为这些值可编辑
            - 字典字段优先转 `PlannerSelect`，确保前端走约束选项而不是自由文本
        """

        if not field.writable:
            return {
                "type": "PlannerMetric",
                "props": {
                    "label": field.name,
                    "value": self._format_form_value(read_state_value(state, field.state_path)),
                    "required": field.required,
                },
            }

        if (
            field.source_kind == "dictionary"
            and field.option_source is not None
            and field.option_source.type == "dict"
            and field.option_source.dict_code
        ):
            return {
                "type": "PlannerSelect",
                "props": {
                    "label": field.name,
                    "dictCode": field.option_source.dict_code,
                    "value": {"$bindState": field.state_path},
                    "required": field.required,
                },
            }

        placeholder = f"请输入{field.name}" if field.value_type in {"string", "number", "boolean"} else f"请输入{field.name}"
        return {
            "type": "PlannerInput",
            "props": {
                "label": field.name,
                "value": {"$bindState": field.state_path},
                "placeholder": placeholder,
                "required": field.required,
            },
        }

    @staticmethod
    def _format_form_value(value: Any) -> str:
        """把只读字段值压成适合 PlannerMetric 展示的字符串。"""

        if value in (None, ""):
            return "-"
        if isinstance(value, list):
            return ", ".join(str(item) for item in value)
        if isinstance(value, dict):
            try:
                return json.dumps(value, ensure_ascii=False)
            except TypeError:
                return str(value)
        return str(value)

    async def _llm_generate_spec(
        self,
        intent: str,
        data: Any,
        context: dict | None,
        runtime: ApiQueryUIRuntime | None,
        *,
        trace_id: str | None = None,
    ) -> dict[str, Any] | None:
        """通过正式 Renderer Prompt 调用 LLM 生成 UI Spec。

        功能：
            第五阶段真正要解决的不是“让模型随便画页面”，而是把用户问题、裁剪后的
            `context_pool`、运行时能力目录三者装配进一个受控 Prompt。这里统一承担：

            1. 构建 Renderer 专用的 system/user messages
            2. 首次强制启用 JSON Mode，失败后再回退到纯文本解析
            3. 对模型脏输出做 JSON 清洗，再交给出口归一化逻辑

        Args:
            intent: 当前渲染意图，例如 `query`、`knowledge`、`task`。
            data: 当前视图最核心的数据载荷，不会在这里被原地修改。
            context: 上游拼装好的渲染上下文，可能包含 `user_query`、`context_pool`、
                `business_intents`、标题及提示文案。
            runtime: 当前前端运行时契约，用于约束可用组件和动作。

        Returns:
            LLM 返回的原始 Spec 字典；若无法稳定生成，则返回 `None` 并由调用方回退规则模式。

        Edge Cases:
            - 某些兼容后端不支持 `response_format`，这里会自动退回普通文本模式再试一次
            - 模型返回 Markdown 包裹、注释、尾逗号等脏 JSON 时，清洗后仍可解析
            - 若模型捏造了非对象输出，直接视为失败，绝不把半成品交给前端
        """
        llm = self._get_llm_service()
        messages = self._build_renderer_messages(intent, data, context, runtime)

        for attempt in range(_LLM_RENDER_MAX_ATTEMPTS):
            use_json_mode = attempt == 0
            try:
                reply = await llm.chat(
                    messages=messages,
                    temperature=0.0,
                    response_format={"type": "json_object"} if use_json_mode else None,
                )
            except Exception as exc:
                logger.warning(
                    "LLM UI Spec 生成失败，trace_id=%s attempt=%s/%s intent=%s json_mode=%s error=%s",
                    trace_id or "-",
                    attempt + 1,
                    _LLM_RENDER_MAX_ATTEMPTS,
                    intent,
                    use_json_mode,
                    exc,
                )
                continue

            spec = self._parse_llm_spec(reply)
            if spec:
                return spec

            logger.warning(
                "LLM UI Spec 返回了不可解析结果，trace_id=%s attempt=%s/%s intent=%s raw=%s",
                trace_id or "-",
                attempt + 1,
                _LLM_RENDER_MAX_ATTEMPTS,
                intent,
                self._summarize_text(reply),
            )
        return None

    def _build_renderer_messages(
        self,
        intent: str,
        data: Any,
        context: dict[str, Any] | None,
        runtime: ApiQueryUIRuntime | None,
    ) -> list[dict[str, str]]:
        """构建第五阶段 Renderer 的消息体。

        功能：
            将“Prompt 模板”和“本次请求的事实输入”拆成 system/user 两段，避免把动态数据
            和静态规则混写到一大串字符串里，方便后续审计和测试断言。
        """
        renderer_payload = self._build_renderer_payload(intent, data, context, runtime)
        user_prompt = (
            "请基于以下输入生成 json-render Spec。必须且只能返回合法 JSON，不要输出解释文字。\n"
            f"{json.dumps(renderer_payload, ensure_ascii=False, indent=2, default=str)}"
        )
        return [
            {"role": "system", "content": self._build_renderer_system_prompt(intent, runtime)},
            {"role": "user", "content": user_prompt},
        ]

    def _build_renderer_system_prompt(self, intent: str, runtime: ApiQueryUIRuntime | None) -> str:
        """构建 Renderer 的系统提示词。

        功能：
            Prompt 的重点不是追求文采，而是建立稳定的“组件白名单 + 数据使用规则”。
            这里按 `query` 与其他旧链路区分，确保 `api_query` 优先收敛到 `Planner*` 原语。

        Edge Cases:
            - `query` 意图会显式强调 `Planner*` 组件和读态规则，防止模型回退到旧组件命名
            - runtime 为空时仍会输出目录占位，避免模型误以为可以自由造动作
        """
        component_catalog = self._format_component_catalog(intent, runtime)
        action_catalog = self._format_action_catalog(runtime)

        if intent == "query":
            return (
                "# Role\n"
                "你是一个资深的智能 UX 架构师 (Renderer Agent)。"
                "你的任务是阅读用户原始请求、分析裁剪后的 context_pool 和主数据，"
                "并在受控组件目录下生成一个符合 json-render 规范的声明式 UI JSON Spec。\n\n"
                "# Input Rules\n"
                "1. 用户原始请求是最高优先级文案来源。\n"
                "2. context_pool 是事实总线，只能基于其中 status/data/error 做渲染，不得臆造缺失数据。\n"
                "3. business_intents 只代表业务意图，不等于前端物理动作；若运行时未启用对应动作，不要生成写操作控件。\n\n"
                "# UI Catalog\n"
                f"{component_catalog}\n\n"
                "# Runtime Actions\n"
                f"{action_catalog}\n\n"
                "# Rendering Rules\n"
                "1. 同质数组优先使用 PlannerTable。\n"
                "2. 单对象详情优先使用 PlannerDetailCard。\n"
                "3. 如果存在局部失败或跳过信息，应使用 PlannerNotice 做显式提示。\n"
                "4. 当前 read_only 链路优先返回 root/state/elements 结构；state 在纯读场景下通常为空对象。\n"
                "5. 严禁捏造未注册的组件、动作、props 或数据字段。\n\n"
                "# Output Constraints\n"
                "必须且只能输出合法的纯 JSON 字符串。不要输出 Markdown、注释、解释性文字。"
            )

        return (
            "# Role\n"
            "你是一个通用 Renderer Agent，需要根据传入数据生成 json-render 兼容 Spec。\n\n"
            "# UI Catalog\n"
            f"{component_catalog}\n\n"
            "# Runtime Actions\n"
            f"{action_catalog}\n\n"
            "# Output Constraints\n"
            "必须只使用已注册组件，直接返回合法 JSON，不要输出 Markdown 或解释文字。"
        )

    def _build_renderer_payload(
        self,
        intent: str,
        data: Any,
        context: dict[str, Any] | None,
        runtime: ApiQueryUIRuntime | None,
    ) -> dict[str, Any]:
        """裁剪并组装喂给 Renderer 的动态输入。

        功能：
            网关返回给前端的 `ui_spec` 可以包含完整展示数据，但喂给 LLM 的输入必须更克制。
            这里单独做 prompt 级裁剪，避免一次请求把整个 `context_pool`、所有分页结果和
            冗长 runtime schema 一起塞进模型窗口。

        Edge Cases:
            - `user_query` 同时兼容 `user_query/question` 两种上下文字段，避免上游旧调用点失效
            - 主数据、context_pool、runtime 都会被二次裁剪，防止 prompt 体积失控
        """
        renderer_context = context or {}
        return {
            "intent": intent,
            "user_query": renderer_context.get("user_query") or renderer_context.get("question"),
            "presentation": {
                "title": renderer_context.get("title"),
                "detail_title": renderer_context.get("detail_title"),
                "render_mode": renderer_context.get("query_render_mode"),
                "empty_message": renderer_context.get("empty_message"),
                "skip_message": renderer_context.get("skip_message"),
                "partial_message": renderer_context.get("partial_message"),
            },
            "business_intents": self._prune_business_intents(renderer_context.get("business_intents")),
            "primary_data": self._prune_renderer_value(data),
            "context_pool": self._prune_context_pool(renderer_context.get("context_pool")),
            "runtime": self._prune_runtime(runtime),
        }

    def _prune_business_intents(self, business_intents: Any) -> list[dict[str, Any]]:
        """裁剪业务意图输入，避免把上游模型对象原封不动再塞给 Renderer。"""
        if not isinstance(business_intents, list):
            return []

        pruned_items: list[dict[str, Any]] = []
        for item in business_intents:
            if isinstance(item, dict):
                pruned_items.append(
                    {
                        "code": item.get("code"),
                        "category": item.get("category"),
                        "risk_level": item.get("risk_level"),
                    }
                )
            else:
                pruned_items.append({"code": str(item)})
        return pruned_items

    def _prune_context_pool(self, context_pool: Any) -> dict[str, Any]:
        """裁剪进入 Renderer 的 `context_pool`。

        功能：
            `context_pool` 是第五阶段最重要的事实输入，但也是最容易导致 token 爆炸的部分。
            这里保留状态机决策所必需的字段，把执行细节、原始参数和大结果集缩减为摘要。

        Edge Cases:
            - 非字典步骤结果会被直接忽略，避免模型看到不可解释的运行时对象
            - meta 只保留渲染决策相关字段，故意不透传完整原始参数，防止 prompt 泄漏实现细节
        """
        if not isinstance(context_pool, dict):
            return {}

        pruned_pool: dict[str, Any] = {}
        for step_id, step_result in context_pool.items():
            if not isinstance(step_result, dict):
                continue

            pruned_step: dict[str, Any] = {
                "status": step_result.get("status"),
                "domain": step_result.get("domain"),
                "api_id": step_result.get("api_id"),
                "total": step_result.get("total"),
                "data": self._prune_renderer_value(step_result.get("data")),
            }
            if isinstance(step_result.get("error"), dict):
                pruned_step["error"] = {
                    "code": step_result["error"].get("code"),
                    "message": step_result["error"].get("message"),
                    "retryable": step_result["error"].get("retryable"),
                }
            if step_result.get("skipped_reason"):
                pruned_step["skipped_reason"] = step_result.get("skipped_reason")

            meta = step_result.get("meta")
            if isinstance(meta, dict):
                pruned_step["meta"] = {
                    "raw_row_count": meta.get("raw_row_count"),
                    "render_row_count": meta.get("render_row_count"),
                    "render_row_limit": meta.get("render_row_limit"),
                    "truncated": meta.get("truncated"),
                    "truncated_count": meta.get("truncated_count"),
                }
            pruned_pool[str(step_id)] = pruned_step
        return pruned_pool

    def _prune_runtime(self, runtime: ApiQueryUIRuntime | None) -> dict[str, Any]:
        """裁剪前端运行时能力目录。

        功能：
            Renderer 需要知道“能用什么”，但不需要把每个动作的完整 Schema 全量记住。
            这里保留组件名、启用动作和关键读态能力，既能做约束，也不会把 prompt 撑大。

        Edge Cases:
            - runtime 为空时回退最小只读能力，避免模型误生成交互动作
            - 列表/详情/表单都会保留 enabled 与关键元数据，兼容不同渲染模式的判定

        Args:
            runtime: 响应层构建的运行时契约。

        Returns:
            供 Renderer 使用的轻量 runtime 目录。
        """
        if runtime is None:
            return {"mode": "read_only", "components": []}

        # 这里有意保留 enabled/api_id/param_source 等“可执行约束字段”，
        # 不保留完整 schema 细节，平衡模型约束与 prompt 体积。
        return {
            "mode": runtime.mode,
            "components": list(runtime.components),
            "ui_actions": [
                {
                    "code": action.code,
                    "description": action.description,
                    "enabled": action.enabled,
                }
                for action in runtime.ui_actions
            ],
            "list": {
                "enabled": runtime.list.enabled,
                "api_id": runtime.list.api_id,
                "route_url": runtime.list.route_url,
                "ui_action": runtime.list.ui_action,
                "param_source": runtime.list.param_source,
                "pagination": {
                    "enabled": runtime.list.pagination.enabled,
                    "total": runtime.list.pagination.total,
                    "current_page": runtime.list.pagination.current_page,
                    "page_size": runtime.list.pagination.page_size,
                    "page_param": runtime.list.pagination.page_param,
                    "page_size_param": runtime.list.pagination.page_size_param,
                    "mutation_target": runtime.list.pagination.mutation_target,
                },
                "filters": {
                    "enabled": runtime.list.filters.enabled,
                    "fields": [field.model_dump(exclude_none=True) for field in runtime.list.filters.fields],
                },
                "query_context": {
                    "enabled": runtime.list.query_context.enabled,
                    "current_params": dict(runtime.list.query_context.current_params),
                    "page_param": runtime.list.query_context.page_param,
                    "page_size_param": runtime.list.query_context.page_size_param,
                    "preserve_on_pagination": list(runtime.list.query_context.preserve_on_pagination),
                    "reset_page_on_filter_change": runtime.list.query_context.reset_page_on_filter_change,
                },
            },
            "detail": {
                "enabled": runtime.detail.enabled,
                "api_id": runtime.detail.api_id,
                "route_url": runtime.detail.route_url,
                "ui_action": runtime.detail.ui_action,
                "request": runtime.detail.request.model_dump(exclude_none=True),
                "source": runtime.detail.source.model_dump(exclude_none=True),
            },
            "form": {
                "enabled": runtime.form.enabled,
                "form_code": runtime.form.form_code,
                "mode": runtime.form.mode,
                "api_id": runtime.form.api_id,
                "route_url": runtime.form.route_url,
                "ui_action": runtime.form.ui_action,
                "state_path": runtime.form.state_path,
                "fields": [field.model_dump(exclude_none=True) for field in runtime.form.fields],
                "submit": runtime.form.submit.model_dump(exclude_none=True),
            },
            "audit": {
                "enabled": runtime.audit.enabled,
                "snapshot_required": runtime.audit.snapshot_required,
                "risk_level": runtime.audit.risk_level,
            },
        }

    def _prune_renderer_value(self, value: Any, *, depth: int = 0) -> Any:
        """对任意值做 prompt 级压缩。

        功能：
            规则渲染可以消费完整裁剪结果，LLM Renderer 则更怕无关噪音。
            这里按深度、字段数和行数做二次收缩，把“足够理解业务”与“避免 token 爆炸”
            两件事同时兼顾。

        Edge Cases:
            - 深层非标量对象会被折叠成字符串摘要，防止递归结构把 prompt 撑爆
            - 超长字符串、超长数组和超大对象都会按固定阈值截断，保证 prompt 规模可预测

        Args:
            value: 待裁剪的任意值。
            depth: 当前递归深度，用于控制深层对象展开上限。

        Returns:
            裁剪后的值，保持“可解释优先”而非“全量保真”。
        """
        if value is None:
            return None
        if isinstance(value, (bool, int, float)):
            return value
        if isinstance(value, str):
            if len(value) <= _LLM_RENDER_STRING_LIMIT:
                return value
            return f"{value[:_LLM_RENDER_STRING_LIMIT]}..."
        if isinstance(value, list):
            limited_items = value[:_LLM_RENDER_ROW_LIMIT]
            return [self._prune_renderer_value(item, depth=depth + 1) for item in limited_items]
        if isinstance(value, dict):
            pruned_dict: dict[str, Any] = {}
            for index, (key, item) in enumerate(value.items()):
                if index >= _LLM_RENDER_KEY_LIMIT:
                    pruned_dict["__truncated_keys__"] = len(value) - _LLM_RENDER_KEY_LIMIT
                    break
                if depth >= 2 and not isinstance(item, (str, int, float, bool, type(None))):
                    pruned_dict[key] = str(item)[:_LLM_RENDER_STRING_LIMIT]
                    continue
                pruned_dict[key] = self._prune_renderer_value(item, depth=depth + 1)
            return pruned_dict
        return str(value)[:_LLM_RENDER_STRING_LIMIT]

    def _format_component_catalog(self, intent: str, runtime: ApiQueryUIRuntime | None) -> str:
        """格式化当前请求可用的组件目录。"""
        requested_components = list(runtime.components) if runtime and runtime.components else []
        catalog = self._get_catalog_service().get_component_catalog(
            intent=intent,
            requested_codes=requested_components or None,
        )

        component_names = requested_components or list(catalog.keys())
        lines: list[str] = []
        for component_name in component_names:
            description = catalog.get(component_name)
            if description:
                lines.append(f"- `{component_name}`: {description}")
        return "\n".join(lines) or "- 当前未注册可用组件"

    @staticmethod
    def _format_action_catalog(runtime: ApiQueryUIRuntime | None) -> str:
        """格式化当前请求可用的动作目录。"""
        if runtime is None or not runtime.ui_actions:
            return "- 当前未注册可用动作"

        lines = []
        for action in runtime.ui_actions:
            state = "enabled" if action.enabled else "disabled"
            lines.append(f"- `{action.code}` ({state}): {action.description}")
        return "\n".join(lines)

    def _parse_llm_spec(self, raw_reply: str) -> dict[str, Any] | None:
        """从 Renderer 原始输出中提取首个 JSON 对象。"""
        if not raw_reply:
            return None

        json_text = extract_first_json_object_text(raw_reply)
        if not json_text:
            return None

        parsed = load_json_object(json_text)
        if not parsed and json_text.strip() != "{}":
            logger.debug("Failed to parse renderer json: %s", raw_reply[:200])
            return None

        return parsed

    def _normalize_spec_shape(self, spec: dict[str, Any] | None) -> dict[str, Any] | None:
        """将第五阶段输出统一折叠为 flat spec。

        功能：
            当前 `ai-gateway` 正处于旧树形 Spec 向 `root/state/elements` 过渡的阶段。
            这里把所有出口统一成 flat spec，目的是让 route 层、测试和后续 `json-render`
            主链只消费一套结构，而不是继续在边界层维护双协议。

        Args:
            spec: 规则模式或 LLM 模式生成的原始 Spec。

        Returns:
            标准化后的 flat spec；若输入无法识别，则返回 `None`。

        Edge Cases:
            - 已经是 flat spec 时只补齐空 `state`
            - 旧树形 Spec 会被稳定转换，元素 ID 使用确定性命名，便于测试断言和快照比对
        """
        if not isinstance(spec, dict):
            return None

        if self._is_flat_spec(spec):
            state = spec.get("state")
            return {
                **spec,
                "state": state if isinstance(state, dict) else {},
            }

        if "type" not in spec:
            return None

        return self._legacy_tree_to_flat_spec(spec)

    @staticmethod
    def _is_flat_spec(spec: dict[str, Any]) -> bool:
        """判断当前 Spec 是否已经符合 `root/state/elements` 契约。"""
        return isinstance(spec.get("root"), str) and isinstance(spec.get("elements"), dict)

    def _legacy_tree_to_flat_spec(self, root_node: dict[str, Any]) -> dict[str, Any]:
        """把旧树形 UI 结构转换成 flat spec。

        功能：
            任务 1 的目标是“先统一契约，再继续演进组件语义”。因此这里不重写现有规则
            渲染逻辑，而是在出口做一次结构归一化，让旧实现也能立刻进入新协议。

        Args:
            root_node: 旧版 `type/props/children` 根节点。

        Returns:
            `root/state/elements` 形态的 flat spec。

        Edge Cases:
            - 仅递归转换真正的子组件树，不会错误下钻到 `props.actions` 这类配置数组
            - 子元素 ID 采用确定性前缀 + 递增序号，避免每次生成随机 ID 造成测试抖动
        """
        element_counter = 0
        elements: dict[str, Any] = {}

        def next_element_id(node_type: Any) -> str:
            nonlocal element_counter
            element_counter += 1
            prefix = self._build_element_id_prefix(node_type)
            return f"{prefix}_{element_counter}"

        def materialize(node: dict[str, Any], *, element_id: str) -> None:
            element_payload = {key: value for key, value in node.items() if key != "children"}
            raw_children = node.get("children")
            child_ids: list[str] = []

            if isinstance(raw_children, list):
                for child in raw_children:
                    if not isinstance(child, dict) or "type" not in child:
                        continue
                    child_id = next_element_id(child.get("type"))
                    child_ids.append(child_id)
                    materialize(child, element_id=child_id)

            if child_ids:
                element_payload["children"] = child_ids

            elements[element_id] = element_payload

        root_id = "root"
        materialize(root_node, element_id=root_id)
        return {
            "root": root_id,
            "state": {},
            "elements": elements,
        }

    @staticmethod
    def _build_element_id_prefix(node_type: Any) -> str:
        """生成稳定的元素 ID 前缀。

        功能：
            这里故意不用 UUID。第五阶段 Spec 在测试、日志和审计快照里都需要可对比性，
            稳定前缀能显著降低调试噪音。
        """
        normalized = re.sub(r"[^a-z0-9]+", "_", str(node_type or "element").strip().lower()).strip("_")
        return normalized or "element"

    def _knowledge_spec(self, results: list[KnowledgeResult], context: dict | None) -> dict[str, Any]:
        """把知识检索结果渲染成列表卡片。

        功能：
            知识检索链路仍沿用旧组件，但这里保留稳定的卡片/列表组织方式，确保未来迁移
            `Planner*` 组件前，前端也能消费统一结构。

        Edge Cases:
            - metadata 缺失时会回退默认来源与空标签，避免页面出现 `None`
            - 内容摘要只截取前 160 字，防止知识正文撑爆列表视图
        """
        items = [
            {
                "id": result.doc_id,
                "title": result.title,
                "description": result.content[:160],
                "status": result.doc_type,
                "tags": [
                    {"label": result.doc_type or "知识库", "color": "blue"},
                    *(
                        [{"label": tag, "color": "purple"} for tag in result.metadata.get("tags", [])]
                        if isinstance(result.metadata, dict)
                        else []
                    ),
                ],
                "meta": {
                    "source": result.metadata.get("source") if isinstance(result.metadata, dict) else "知识库",
                    "score": f"{result.score:.2f}",
                },
            }
            for result in results
        ]
        return {
            "type": "Card",
            "props": {
                "title": (context or {}).get("title", "知识检索结果"),
                "subtitle": f"命中 {len(items)} 条",
                "actions": [
                    {"type": "view_detail", "label": "查看来源"},
                    {"type": "refresh", "label": "刷新"},
                ],
            },
            "children": [
                {
                    "type": "List",
                    "props": {"title": "相关知识", "items": items, "emptyText": "暂无匹配内容"},
                }
            ],
        }

    def _query_spec(
        self,
        rows: list[dict[str, Any]],
        context: dict | None,
        runtime: ApiQueryUIRuntime | None,
        *,
        include_partial_notice: bool = False,
    ) -> dict[str, Any]:
        """把结构化查询结果渲染成 `Planner*` 读态视图。

        功能：
            第五阶段任务 2 的目标不是“让页面更花哨”，而是把 `api_query` 的读态输出
            收口到稳定的宏观原语：

            - 同质列表 → `PlannerTable`
            - 单对象详情 → `PlannerDetailCard`
            - 局部失败提示 → `PlannerNotice`

            这样做的核心收益是：先把网关对外的 UI 语言稳定下来，后续无论是规则渲染
            还是 LLM Renderer，都不需要再围绕旧的 `Card/Table/Notice` 兼容层打补丁。

        Args:
            rows: 已经过网关裁剪后的结果行。
            context: `api_query` 传入的渲染上下文，包含标题、提示语和渲染模式。
            runtime: 当前查询的运行时动作与交互能力。
            include_partial_notice: 是否需要在成功内容前额外挂载一条局部成功提示。

        Returns:
            `root/state/elements` 形态的 flat spec。

        Edge Cases:
            - 单条列表结果不自动升格为详情卡，只有 route 层显式标记 `detail` 才切详情视图
            - 多步骤摘要表仍然走 `PlannerTable`，但会通过 notice 显式暴露“只展示安全结果”
        """
        # 1. 先冻结页面级文案：标题、副标题、局部失败提示统一在根卡片收口。
        render_mode = (context or {}).get("query_render_mode") or "table"
        label_index = self._build_response_field_label_index(context)
        root_props = {
            "title": (context or {}).get("question", "数据查询结果"),
            "subtitle": self._build_query_subtitle(rows, context, render_mode),
        }
        if include_partial_notice:
            partial_message = (context or {}).get("partial_message", "部分步骤执行失败，当前仅展示成功返回的数据。")
            subtitle = root_props.get("subtitle")
            root_props["subtitle"] = f"{subtitle} · {partial_message}" if subtitle else partial_message

        # 2. detail/composite 属于显式渲染模式，优先分流，避免被后续表格兜底覆盖。
        if render_mode == "detail":
            detail_view_meta = (
                runtime.detail.detail_view_meta
                if runtime and isinstance(runtime.detail.detail_view_meta, dict)
                else None
            )
            detail_props = {
                "title": (context or {}).get("detail_title", "详情信息"),
                "items": self._build_detail_items(
                    rows[0],
                    label_index=label_index,
                    detail_view_meta=detail_view_meta,
                ),
            }
            if runtime and runtime.detail.enabled and runtime.detail.api_id:
                detail_identifier_field = runtime.detail.source.identifier_field
                detail_identifier_param = runtime.detail.request.identifier_param or detail_identifier_field
                if detail_identifier_field and detail_identifier_param:
                    detail_props.update(
                        _build_runtime_request_fields(
                            runtime.detail.api_id,
                            param_source=runtime.detail.request.param_source,
                            params={detail_identifier_param: rows[0].get(detail_identifier_field)},
                            flow_num=(context or {}).get("flow_num"),
                            created_by=(context or {}).get("created_by"),
                            request_schema_fields=runtime.detail.request.request_schema_fields,
                        )
                    )
            return self._build_flat_card_spec(
                root_props=root_props,
                children=[
                    {
                        "type": "PlannerDetailCard",
                        "props": detail_props,
                    }
                ],
            )

        if render_mode == "composite":
            return self._build_query_composite_spec(
                row=rows[0] if rows else {},
                root_props=root_props,
                context=context,
                runtime=runtime,
                label_index=label_index,
            )

        # 仅当结果本身是单对象时才回退详情卡。对多行数据仍应保留表格渲染，
        # 否则 LLM 失败后的规则兜底会把列表误折叠成详情卡，破坏既有列表语义。
        if not (runtime and runtime.list.enabled) and len(rows) <= 1:
            detail_view_meta = (
                runtime.detail.detail_view_meta
                if runtime and isinstance(runtime.detail.detail_view_meta, dict)
                else None
            )
            return self._build_flat_card_spec(
                root_props=root_props,
                children=[
                    {
                        "type": "PlannerDetailCard",
                        "props": {
                            "title": (context or {}).get("detail_title", "详情信息"),
                            "items": self._build_detail_items(
                                rows[0] if rows else {},
                                label_index=label_index,
                                detail_view_meta=detail_view_meta,
                            ),
                        },
                    }
                ],
            )

        # 3. table 视图：先构建筛选状态与请求模板，再组装查询/重置/分页动作。
        filters_state = _build_query_filter_state(runtime)
        filter_fields = list(runtime.list.filters.fields) if runtime else []
        current_params = dict(runtime.list.query_context.current_params) if runtime else {}
        list_request_fields = _build_runtime_request_fields(
            runtime.list.api_id if runtime else None,
            param_source=runtime.list.param_source if runtime else None,
            params=current_params,
            flow_num=(context or {}).get("flow_num"),
            created_by=(context or {}).get("created_by"),
            request_schema_fields=runtime.list.request_schema_fields if runtime else None,
        )
        filter_submit_request_fields = _build_runtime_request_fields(
            runtime.list.api_id if runtime else None,
            param_source=runtime.list.param_source if runtime else None,
            params=_build_filter_submit_params(runtime, filter_fields),
            flow_num=(context or {}).get("flow_num"),
            created_by=(context or {}).get("created_by"),
            request_schema_fields=runtime.list.request_schema_fields if runtime else None,
        )
        filter_reset_request_fields = _build_runtime_request_fields(
            runtime.list.api_id if runtime else None,
            param_source=runtime.list.param_source if runtime else None,
            params=_build_filter_reset_params(runtime, filter_fields),
            flow_num=(context or {}).get("flow_num"),
            created_by=(context or {}).get("created_by"),
            request_schema_fields=runtime.list.request_schema_fields if runtime else None,
        )

        elements: dict[str, Any] = {
            "root": {
                "type": "PlannerCard",
                "props": root_props,
                "children": ["query-filters", "report-table", "report-pagination"],
            },
            "query-filters": {
                "type": "PlannerForm",
                "props": {
                    "formCode": "query_filters",
                    **list_request_fields,
                },
                "children": [],
            },
        }

        for index, field in enumerate(filter_fields, start=1):
            element_id = f"filter_field_{index}"
            elements["query-filters"]["children"].append(element_id)
            elements[element_id] = self._build_query_filter_element(field)

        if runtime and runtime.list.enabled:
            elements["filter_reset"] = {
                "type": "PlannerButton",
                "props": {"label": "重置"},
                "on": {
                    "press": {
                        "action": runtime.list.ui_action or "remoteQuery",
                        "params": {
                            "api_id": runtime.list.api_id,
                            **filter_reset_request_fields,
                        },
                    }
                },
            }
            elements["filter_submit"] = {
                "type": "PlannerButton",
                "props": {"label": "查询"},
                "on": {
                    "press": {
                        "action": runtime.list.ui_action or "remoteQuery",
                        "params": {
                            "api_id": runtime.list.api_id,
                            **filter_submit_request_fields,
                        },
                    }
                },
            }
            elements["query-filters"]["children"].extend(["filter_reset", "filter_submit"])

        configured_table_fields = runtime.list.table_fields if runtime else None
        table_rows = self._build_table_rows(rows, configured_fields=configured_table_fields)
        table_props: dict[str, Any] = {
            "columns": self._build_table_columns(
                table_rows[0],
                label_index=label_index,
                configured_fields=configured_table_fields,
            ),
            "dataSource": table_rows,
            **list_request_fields,
        }
        context_row_actions = (context or {}).get("row_actions")
        if isinstance(context_row_actions, list) and context_row_actions:
            # 上游显式动作优先级最高（例如 WAIT_SELECT 场景），避免被默认详情动作覆盖。
            table_props["rowActions"] = self._normalize_row_actions(context_row_actions)
        elif runtime and runtime.detail.enabled:
            # 详情动作只下发运行时契约，不在网关 UI 层硬编码具体业务参数。
            detail_runtime_strategy_fields = self._build_detail_runtime_strategy_fields(runtime)
            table_props["rowActions"] = [
                {
                    "action": runtime.detail.ui_action or "remoteQuery",
                    "label": "查看详情",
                    "params": {
                        "api_id": runtime.detail.api_id,
                        **detail_runtime_strategy_fields,
                        **_build_runtime_request_fields(
                            runtime.detail.api_id,
                            param_source=runtime.detail.request.param_source,
                            params={
                                (runtime.detail.request.identifier_param or runtime.detail.source.identifier_field): {
                                    "$bindRow": runtime.detail.source.identifier_field
                                }
                            },
                            flow_num=(context or {}).get("flow_num"),
                            created_by=(context or {}).get("created_by"),
                            request_schema_fields=runtime.detail.request.request_schema_fields,
                        ),
                    },
                }
            ]
        elements["report-table"] = {"type": "PlannerTable", "props": table_props}
        elements["report-pagination"] = {
            "type": "PlannerPagination",
            "props": {
                "enabled": runtime.list.pagination.enabled if runtime else False,
                "total": runtime.list.pagination.total if runtime else len(rows),
                "currentPage": runtime.list.pagination.current_page if runtime else None,
                "pageSize": runtime.list.pagination.page_size if runtime else None,
                "pageParam": runtime.list.pagination.page_param if runtime else None,
                "pageSizeParam": runtime.list.pagination.page_size_param if runtime else None,
                **list_request_fields,
            },
        }

        return {
            "root": "root",
            "state": {"filters": filters_state},
            "elements": elements,
        }

    @staticmethod
    def _build_detail_runtime_strategy_fields(runtime: ApiQueryUIRuntime) -> dict[str, Any]:
        """提取详情跳转所需的模板优先/动态兜底策略字段。"""

        detail_runtime = runtime.detail
        params: dict[str, Any] = {
            "renderMode": detail_runtime.render_mode or "dynamic_ui",
            "fallbackMode": detail_runtime.fallback_mode or "dynamic_ui",
        }
        if detail_runtime.template_code:
            params["templateCode"] = detail_runtime.template_code
        return params

    @staticmethod
    def _build_query_filter_element(field: ApiQueryListFilterFieldRuntime) -> dict[str, Any]:
        """将筛选字段 runtime 契约映射为具体组件。

        功能：
            `list_view_meta.filter_fields.component` 的设计目标不是装饰性配置，而是让目录元数据
            真正控制首屏筛选控件形态。这里仅开放当前渲染层已具备稳定语义的三类组件：
            `input / number / select`。

        Args:
            field: 已归一化的筛选字段 runtime。

        Returns:
            单个筛选组件的 flat spec 节点。

        Edge Cases:
            - 未知组件值统一回退为 `PlannerInput`，保证旧数据或脏数据不打断列表页渲染
            - `select` 目前只表达组件语义，不强制要求 options；后续可再补 dict/options 源
        """

        bind_state = {"$bindState": f"/filters/{field.name}"}
        if field.component == "select":
            return {
                "type": "PlannerSelect",
                "props": {
                    "label": field.label,
                    "value": bind_state,
                    "placeholder": f"请选择{field.label}",
                    "required": field.required,
                },
            }

        input_mode = "number" if field.component == "number" else "text"
        return {
            "type": "PlannerInput",
            "props": {
                "label": field.label,
                "value": bind_state,
                "placeholder": f"请输入{field.label}",
                "required": field.required,
                "inputMode": input_mode,
            },
        }

    def _notice_spec(self, title: str, message: str, tone: str) -> dict[str, Any]:
        """构造统一 `PlannerNotice` 读态卡片。

        功能：
            任务 2 之后，读态异常不再继续沿用旧的 `Notice` 组件名。
            这里统一输出 `PlannerCard + PlannerNotice`，确保空结果、错误和跳过场景
            与正常读态页面使用同一套组件语义。
        """
        return self._build_flat_card_spec(
            root_props={"title": title, "subtitle": None},
            children=[
                {
                    "type": "PlannerNotice",
                    "props": {
                        "text": message,
                        "tone": tone,
                    },
                }
            ],
        )

    def _frozen_spec(self, context: dict[str, Any] | None) -> dict[str, Any]:
        """构造冻结当前操作视图的系统级兜底 Spec。

        功能：
            当第五阶段发现组件、动作或绑定不可信时，绝不能把半成品表单交给前端。
            这里统一返回无任何交互入口的提示卡，守住“不误写数据”的最后红线。
        """
        title = (context or {}).get("title", "界面已安全冻结")
        return self._build_flat_card_spec(
            root_props={"title": title, "subtitle": None},
            children=[
                {
                    "type": "PlannerNotice",
                    "props": {
                        "text": "界面渲染组件存在异常，为保障您的数据安全，已冻结当前操作视图。",
                        "tone": "info",
                    },
                }
            ],
        )

    def _task_spec(self, tasks: list[dict[str, Any]]) -> dict[str, Any]:
        """将待办列表渲染成带筛选器的工作台视图。

        功能：
            task 视图仍是旧链路遗留能力，这里保持“筛选器 + 列表”结构稳定，避免旧页面在
            新渲染器接入后突然失去工作台语义。

        Edge Cases:
            - 缺失 `id/title/status` 时会回退默认值，保证任务卡片最小可展示
            - 来源系统标签是可选信息，缺失时不会生成空 tag
        """
        items = [
            {
                "id": task.get("id", task.get("sourceId", str(index))),
                "title": task.get("title", "任务"),
                "description": task.get("description", ""),
                "status": task.get("status", "pending"),
                "tags": [
                    {"label": task.get("priority", "普通"), "color": self._priority_color(task.get("priority", ""))},
                    *([{"label": task.get("sourceSystem", ""), "color": "cyan"}] if task.get("sourceSystem") else []),
                ],
                "assignee": task.get("owner"),
                "dueDate": task.get("deadline"),
            }
            for index, task in enumerate(tasks)
        ]
        return {
            "type": "Card",
            "props": {
                "title": "最新待办",
                "subtitle": f"共 {len(items)} 条待办",
                "actions": [
                    {"type": "refresh", "label": "刷新待办"},
                    {"type": "trigger_task", "label": "批量处理"},
                ],
            },
            "children": [
                {
                    "type": "Form",
                    "props": {
                        "fields": [
                            {
                                "name": "status",
                                "label": "状态",
                                "type": "select",
                                "options": [
                                    {"label": "全部", "value": "all"},
                                    {"label": "待处理", "value": "pending"},
                                    {"label": "进行中", "value": "in_progress"},
                                    {"label": "已完成", "value": "completed"},
                                ],
                            },
                            {
                                "name": "system",
                                "label": "来源系统",
                                "type": "select",
                                "options": [
                                    {"label": "全部", "value": "all"},
                                    {"label": "ERP", "value": "erp"},
                                    {"label": "CRM", "value": "crm"},
                                    {"label": "OA", "value": "oa"},
                                    {"label": "预约系统", "value": "reservation"},
                                    {"label": "360系统", "value": "system360"},
                                ],
                            },
                        ],
                        "submitLabel": "筛选",
                    },
                },
                {
                    "type": "List",
                    "props": {"title": "任务列表", "items": items, "emptyText": "暂无待办"},
                },
            ],
        }

    def _build_flat_card_spec(
        self,
        *,
        root_props: dict[str, Any],
        children: list[dict[str, Any]],
        state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """构造 `PlannerCard` 根节点的 flat spec。

        功能：
            第五阶段后续还会继续引入 `PlannerForm / PlannerSelect / PlannerButton`。
            先把 flat spec 的根结构抽成一个 helper，后面任务 3、4、5 可以直接复用，
            避免每次都手搓 `root/elements` 造成协议细节再次分散。

        Args:
            root_props: 根卡片展示属性。
            children: 已准备好的子元素列表。
            state: 当前视图初始状态；读态页面通常为空对象。

        Returns:
            合法的 `root/state/elements` flat spec。

        Edge Cases:
            - `state=None` 时统一回退空对象，避免前端处理两套状态空值语义
            - 子元素 ID 按顺序编号，保证快照和测试断言稳定
        """
        elements: dict[str, Any] = {
            "root": {
                "type": "PlannerCard",
                "props": root_props,
                "children": [],
            }
        }
        for index, child in enumerate(children, start=1):
            child_id = f"child_{index}"
            elements["root"]["children"].append(child_id)
            elements[child_id] = child
        return {
            "root": "root",
            "state": state or {},
            "elements": elements,
        }

    @staticmethod
    def _normalize_row_actions(row_actions: list[Any]) -> list[Any]:
        """把行动作统一归一到 `action` 字段，并兼容历史 `type` 输入。"""

        normalized_actions: list[Any] = []
        for row_action in row_actions:
            if not isinstance(row_action, dict):
                normalized_actions.append(row_action)
                continue
            normalized = deepcopy(row_action)
            action_name = normalized.get("action")
            legacy_action = normalized.get("type")
            if not isinstance(action_name, str) and isinstance(legacy_action, str):
                normalized["action"] = legacy_action
            if normalized.get("action"):
                normalized.pop("type", None)
            normalized_actions.append(normalized)
        return normalized_actions

    @staticmethod
    def _format_validation_errors(validation: UISpecValidationResult) -> str:
        """压缩 Guard 错误列表，便于日志追踪。"""
        if not validation.errors:
            return "[]"
        items = [f"{error.code}@{error.path}" for error in validation.errors[:5]]
        if len(validation.errors) > 5:
            items.append(f"...(+{len(validation.errors) - 5})")
        return "[" + ", ".join(items) + "]"

    @staticmethod
    def _summarize_payload(payload: dict[str, Any] | None) -> str:
        """压缩 Spec 日志摘要，避免把整页 JSON 打进日志。"""
        if not payload:
            return "<empty>"
        try:
            text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        except TypeError:
            text = str(payload)
        return DynamicUIService._summarize_text(text)

    @staticmethod
    def _summarize_text(text: str | None, *, limit: int = 240) -> str:
        """压缩文本日志长度，保留定位非法输出所需的首段上下文。"""
        normalized = re.sub(r"\s+", " ", (text or "").strip())
        if len(normalized) <= limit:
            return normalized
        return f"{normalized[:limit]}..."

    @staticmethod
    def _build_table_columns(
        sample_row: dict[str, Any],
        *,
        label_index: dict[str, str] | None = None,
        field_path_prefix: str = "",
        configured_fields: list[Any] | None = None,
    ) -> list[dict[str, str]]:
        """把行对象字段映射成 `PlannerTable.columns`。

        功能：
            这里输出稳定的列元数据而不是裸字符串，是为了给后续前端表格实现预留
            `title / dataIndex / key` 三元组契约，避免任务 2 做完后任务 5 又得返工改列结构。
        """
        resolved_label_index = label_index or {}
        columns: list[dict[str, str]] = []
        # 业务原因：当 runtime 已经显式下发 table_fields 时，列表列必须严格按白名单渲染，
        # 不能再由首行数据“猜”列，否则会出现配置失效和敏感字段意外曝光。
        if configured_fields:
            for configured_field in configured_fields:
                key = str(getattr(configured_field, "name", "") or "").strip()
                if not key:
                    continue
                field_path = f"{field_path_prefix}.{key}" if field_path_prefix else key
                configured_title = getattr(configured_field, "title", None)
                title = (
                    configured_title.strip()
                    if isinstance(configured_title, str) and configured_title.strip()
                    else DynamicUIService._resolve_field_label(
                        field_name=key,
                        label_index=resolved_label_index,
                        field_path=field_path,
                    )
                )
                columns.append(
                    {
                        "key": key,
                        "title": title,
                        "dataIndex": key,
                    }
                )
            return columns

        for key in sample_row.keys():
            field_path = f"{field_path_prefix}.{key}" if field_path_prefix else key
            columns.append(
                {
                    "key": key,
                    "title": DynamicUIService._resolve_field_label(
                        field_name=key,
                        label_index=resolved_label_index,
                        field_path=field_path,
                    ),
                    "dataIndex": key,
                }
            )
        return columns

    @staticmethod
    def _build_table_rows(
        rows: list[dict[str, Any]],
        *,
        configured_fields: list[Any] | None = None,
    ) -> list[dict[str, Any]]:
        """按列表列元数据补齐表格派生列。

        功能：
            组合列是 UI 展示层能力，不应该污染业务接口原始响应。这里复制行对象后写入
            `__combined_N` 这类派生字段，让 `PlannerTable.columns.dataIndex` 仍保持简单字符串，
            前端无需理解组合列规则也能稳定展示。
        """
        if not configured_fields:
            return rows

        rendered_rows: list[dict[str, Any]] = []
        for row in rows:
            rendered_row = dict(row)
            for field in configured_fields:
                source_fields = list(getattr(field, "source_fields", []) or [])
                if not source_fields:
                    continue
                column_key = str(getattr(field, "name", "") or "").strip()
                if not column_key:
                    continue
                rendered_row[column_key] = DynamicUIService._compose_table_field_value(row, field)
            rendered_rows.append(rendered_row)
        return rendered_rows

    @staticmethod
    def _compose_table_field_value(row: dict[str, Any], field: Any) -> str:
        """把组合列来源字段折叠成单元格文本。

        功能：
            组合列用于“省市区”“主诊-主责-主治”等弱结构展示。空值应被跳过，只有
            所有来源字段都为空时才显示 `empty_value`，避免出现连续分隔符或无意义空白。
        """
        source_fields = list(getattr(field, "source_fields", []) or [])
        separator = getattr(field, "separator", "")
        empty_value = getattr(field, "empty_value", "-")
        values: list[str] = []
        for source_field in source_fields:
            value = row.get(source_field)
            if value is None or value == "":
                continue
            values.append(DynamicUIService._stringify_detail_value(value))
        return str(separator).join(values) if values else str(empty_value or "-")

    @staticmethod
    def _build_detail_items(
        row: dict[str, Any],
        *,
        label_index: dict[str, str] | None = None,
        field_path_prefix: str = "",
        detail_view_meta: dict[str, Any] | None = None,
    ) -> list[dict[str, str]]:
        """把对象详情映射成 `PlannerDetailCard.items`。

        功能：
            详情视图的目标是“稳定展示事实”，不是透传原始对象结构。
            对复杂嵌套结构仍保持跳过，避免把结构化明细压成超长字符串；
            但 `list[string]` 这类“多值标签集合”在健康档案、风险标签等详情页里非常常见，
            若一律跳过会导致元数据虽已声明展示字段，用户却完全看不到内容。因此这里单独
            放通“标量数组”，统一折叠为一行文本；真正的 `list[object]` / `dict` 仍交给
            composite 模式拆分成表格或指标区展示。
        """
        resolved_label_index = label_index or {}
        items = []
        # 1. 先挑选“可展示字段集合”：优先尊重 detail_view_meta，再回退历史自动规则。
        selected_fields = DynamicUIService._select_detail_fields(
            row=row,
            detail_view_meta=detail_view_meta,
        )
        for key in selected_fields:
            value = row.get(key)
            # 业务原因：详情卡允许 `list[string]` 这类轻量多值字段按“标签集合”展示，
            # 但必须继续拦截 dict / list[object]，避免把结构化数据错误压平成难读长串。
            if isinstance(value, dict) or DynamicUIService._is_non_scalar_detail_list(value):
                continue
            field_path = f"{field_path_prefix}.{key}" if field_path_prefix else key
            items.append(
                {
                    "label": DynamicUIService._resolve_field_label(
                        field_name=key,
                        label_index=resolved_label_index,
                        field_path=field_path,
                    ),
                    "value": DynamicUIService._stringify_detail_value(value),
                }
            )
        return items or [{"label": "提示", "value": "暂无可展示的标量字段"}]

    @staticmethod
    def _select_detail_fields(
        *,
        row: dict[str, Any],
        detail_view_meta: dict[str, Any] | None,
    ) -> list[str]:
        """按详情元数据挑选最终展示字段。

        功能：
            该方法把 `detail_view_meta` 的四个字段转换成可执行规则，确保详情页展示行为稳定可审计。

        Args:
            row: 当前详情对象。
            detail_view_meta: 详情元数据字典（display/required/exclude/groups）。

        Returns:
            最终展示字段顺序列表。

        Edge Cases:
            - 元数据缺失或全空：回退到历史行为（按对象 key 顺序）
            - display/required 都配置但全被 exclude 覆盖：返回空列表，由上层输出“暂无字段”提示
        """

        if not row:
            return []
        if not isinstance(detail_view_meta, dict):
            return list(row.keys())

        # 1. 先归一化元数据字段，过滤脏值，保证后续集合运算不会被异常输入污染。
        display_fields = DynamicUIService._normalize_meta_field_list(detail_view_meta.get("display_fields"))
        required_fields = DynamicUIService._normalize_meta_field_list(detail_view_meta.get("required_fields"))
        exclude_fields = set(DynamicUIService._normalize_meta_field_list(detail_view_meta.get("exclude_fields")))
        groups = detail_view_meta.get("groups")

        if not display_fields and not required_fields and not exclude_fields:
            return list(row.keys())

        # 2. 字段准入优先级固定为：exclude > required > display。
        allowed_fields: list[str] = []
        for field_name in required_fields + display_fields:
            if field_name not in row or field_name in exclude_fields:
                continue
            if field_name not in allowed_fields:
                allowed_fields.append(field_name)

        if not allowed_fields:
            return []

        # 3. groups 只控制布局顺序，不参与字段准入。这里按分组顺序重排已有字段。
        if not isinstance(groups, list):
            return allowed_fields
        ordered_fields: list[str] = []
        for group in groups:
            if not isinstance(group, dict):
                continue
            for field_name in DynamicUIService._normalize_meta_field_list(group.get("fields")):
                if field_name in allowed_fields and field_name not in ordered_fields:
                    ordered_fields.append(field_name)
        for field_name in allowed_fields:
            if field_name not in ordered_fields:
                ordered_fields.append(field_name)
        return ordered_fields

    @staticmethod
    def _normalize_meta_field_list(raw_fields: Any) -> list[str]:
        """将元数据字段列表归一化为去重后的字段名数组。"""

        if not isinstance(raw_fields, list):
            return []
        normalized: list[str] = []
        for item in raw_fields:
            if not isinstance(item, str):
                continue
            field_name = item.strip()
            if not field_name or field_name in normalized:
                continue
            normalized.append(field_name)
        return normalized

    @staticmethod
    def _stringify_detail_value(value: Any) -> str:
        """将详情值折叠为可展示文本。

        功能：
            详情卡本质上是“单值事实面板”，因此这里会把可安全压平的值统一转成字符串。
            其中 `list[string] / list[number] / list[bool]` 统一用顿号拼接，满足中文场景下
            多标签字段的紧凑阅读需求；复杂对象数组则由上游 `_build_detail_items` 继续拦截。

        Edge Cases:
            - 空数组统一展示为 `-`，避免前端出现空白值
            - 数组里夹杂空串/None 时自动过滤，减少由脏数据造成的多余分隔符
        """
        if value is None:
            return "-"
        if isinstance(value, bool):
            return "是" if value else "否"
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, str):
            return value
        if isinstance(value, list):
            scalar_items = [DynamicUIService._stringify_detail_value(item) for item in value if item not in (None, "")]
            return "、".join(item for item in scalar_items if item and item != "-") or "-"
        return str(value)

    @staticmethod
    def _is_non_scalar_detail_list(value: Any) -> bool:
        """判断详情字段是否属于不应在详情卡压平展示的复杂数组。

        功能：
            `PlannerDetailCard` 只适合展示轻量事实值。这里把数组再分成两类：
            1. 标量数组：允许继续展示，例如异常指标、标签、症状清单；
            2. 复杂数组：必须拦截，例如 `list[object]`、嵌套数组、混合结构脏数据。

        Args:
            value: 待判断的字段值。

        Returns:
            `True` 表示应跳过该字段；`False` 表示可以交给 `_stringify_detail_value` 压平展示。

        Edge Cases:
            - 空数组视为可展示，最终会被格式化为 `-`
            - 混入 dict/list 的脏数组按复杂结构处理，避免输出不可预测字符串
        """

        if not isinstance(value, list):
            return False
        for item in value:
            if item is None:
                continue
            if isinstance(item, (str, int, float, bool)):
                continue
            return True
        return False

    @staticmethod
    def _build_query_subtitle(
        rows: list[dict[str, Any]],
        context: dict[str, Any] | None,
        render_mode: str,
    ) -> str | None:
        """为读态查询页面生成副标题。

        功能：
            `PlannerCard` 的 `subtitle` 是读态页面补充上下文的关键位置。
            这里把“当前是详情还是列表”和“展示条数”压成一句稳定文案，帮助用户快速建立心智。
        """
        total = (context or {}).get("total")
        if render_mode == "detail":
            return "当前展示单条记录详情"
        if render_mode == "composite":
            return "当前展示复合结果（概览指标 + 明细列表）"
        if render_mode == "summary_table":
            return f"当前展示 {len(rows)} 个执行步骤的汇总结果"
        if isinstance(total, int) and total > len(rows):
            return f"共 {total} 条，当前展示 {len(rows)} 条"
        return f"当前展示 {len(rows)} 条"

    def _build_query_composite_spec(
        self,
        *,
        row: dict[str, Any],
        root_props: dict[str, Any],
        context: dict[str, Any] | None,
        runtime: ApiQueryUIRuntime | None,
        label_index: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """把单对象复合结果拆分成指标和明细表。

        功能：
            复合结果常见于“一个 summary + 多个 records 列表”的查询语义。
            若继续复用 detail 模式，会把 nested dict/list 退化成字符串，用户不可读。
            这里按数据形态拆分组件，保持通用且不依赖具体字段命名。

        Args:
            row: 单对象复合结果（通常含 summary 对象 + 多个 records 数组）。
            root_props: 根卡片属性（title/subtitle）。
            context: 渲染上下文。
            runtime: query 运行时契约。
            label_index: response_schema 派生的字段中文名索引。

        Returns:
            flat spec，子节点按“概览指标 + 明细表”组织。

        Edge Cases:
            - 没有可表格化 section 时回退详情卡，避免输出空页面
            - summary 无法推断业务字段名时不强行写入 bizFieldKey
        """

        ctx = context if isinstance(context, dict) else {}
        children: list[dict[str, Any]] = []
        list_request_fields = _build_runtime_request_fields(
            runtime.list.api_id if runtime else None,
            param_source=runtime.list.param_source if runtime else None,
            params=dict(runtime.list.query_context.current_params) if runtime else {},
            flow_num=ctx.get("flow_num"),
            created_by=ctx.get("created_by"),
            request_schema_fields=runtime.list.request_schema_fields if runtime else None,
        )

        # 1. 先提取标量指标，映射为统一 InfoGrid 概览区。
        scalar_metrics = self._build_composite_metrics(row)
        resolved_label_index = label_index or {}
        summary_field_key = self._infer_composite_summary_field_key(row, scalar_metrics)
        info_grid_items: list[dict[str, str]] = []
        for field_path, field_name, value in scalar_metrics:
            info_grid_items.append(
                {
                    "label": self._resolve_field_label(
                        field_name=field_name,
                        label_index=resolved_label_index,
                        field_path=field_path,
                    ),
                    "value": self._stringify_detail_value(value),
                }
            )

        # 复合视图的概览信息统一收敛为一个 InfoGrid，
        # 避免同一组指标拆成多个 Metric 造成视觉噪声与层级碎片化。
        if info_grid_items:
            children.append(
                {
                    "type": "PlannerInfoGrid",
                    "props": {
                        "items": info_grid_items,
                        **({"bizFieldKey": summary_field_key} if summary_field_key else {}),
                    },
                }
            )

        # 2. 再把列表型 section 下钻为表格，保持每个业务块都有稳定 bizFieldKey。
        section_title_index = self._build_aggregate_section_title_index(ctx)
        for section_name, section_value in row.items():
            table_rows = self._extract_table_rows(section_value)
            if not table_rows:
                continue
            section_field_path = section_name
            children.append(
                {
                    "type": "PlannerTable",
                    "props": {
                        # 聚合渲染优先使用后端下发的 section 标题（接口名称）；
                        # 没有时再回退字段 label 解析，保持旧行为兼容。
                        "title": section_title_index.get(section_name)
                        or self._resolve_field_label(
                            field_name=section_name,
                            label_index=resolved_label_index,
                            field_path=section_field_path,
                        ),
                        "columns": self._build_table_columns(
                            table_rows[0],
                            label_index=resolved_label_index,
                            field_path_prefix=f"{section_name}[]",
                        ),
                        "dataSource": table_rows,
                        "bizFieldKey": section_name,
                        **list_request_fields,
                    },
                }
            )

        # 3. 极端兜底：既无指标也无列表时，至少保留详情卡让用户看到事实内容。
        if not children:
            children.append(
                {
                    "type": "PlannerDetailCard",
                    "props": {
                        "title": ctx.get("detail_title", "详情信息"),
                        "items": self._build_detail_items(row, label_index=resolved_label_index),
                    },
                }
            )
        return self._build_flat_card_spec(root_props=root_props, children=children)

    @staticmethod
    def _build_aggregate_section_title_index(context: dict[str, Any]) -> dict[str, str]:
        """读取聚合 section 标题映射。

        功能：
            把后端基于 API Catalog 产出的 `section -> 接口名称` 映射收敛成安全字典，
            供 composite 渲染优先使用，避免标题退化成技术字段名。

        Args:
            context: 查询渲染上下文。

        Returns:
            仅包含非空字符串键值对的标题映射字典。

        Edge Cases:
            - 缺失或脏值输入时返回空字典，渲染层会回退到原有 label 解析逻辑
        """
        raw_index = context.get("aggregate_section_title_index")
        if not isinstance(raw_index, dict):
            return {}
        normalized: dict[str, str] = {}
        for raw_key, raw_value in raw_index.items():
            if not isinstance(raw_key, str) or not raw_key.strip():
                continue
            if not isinstance(raw_value, str) or not raw_value.strip():
                continue
            normalized[raw_key.strip()] = raw_value.strip()
        return normalized

    @staticmethod
    def _build_response_field_label_index(context: dict[str, Any] | None) -> dict[str, str]:
        """从渲染上下文读取 response_schema 字段显示名索引。"""

        if not isinstance(context, dict):
            return {}
        label_index = context.get("response_field_label_index")
        if not isinstance(label_index, dict):
            return {}

        normalized: dict[str, str] = {}
        for raw_path, raw_label in label_index.items():
            if not isinstance(raw_path, str) or not raw_path.strip():
                continue
            if not isinstance(raw_label, str) or not raw_label.strip():
                continue
            normalized[raw_path.strip()] = raw_label.strip()
        return normalized

    @staticmethod
    def _resolve_field_label(
        *,
        field_name: str,
        label_index: dict[str, str],
        field_path: str,
    ) -> str:
        """解析字段展示名，优先使用 schema description/title。

        业务接口的 response_schema 和真实响应偶尔只存在大小写差异，例如
        schema 声明 `fId`，但响应返回 `fid`。这里必须保留精确匹配优先，
        再做大小写无关兜底，避免此类脏契约让表头退回技术字段名。
        """

        exact_label = label_index.get(field_path) or label_index.get(field_name)
        if exact_label:
            return exact_label

        normalized_field_path = field_path.casefold()
        normalized_field_name = field_name.casefold()
        for raw_path, label in label_index.items():
            normalized_path = raw_path.casefold()
            if normalized_path in {normalized_field_path, normalized_field_name}:
                return label
        return field_name

    @staticmethod
    def _extract_table_rows(value: Any) -> list[dict[str, Any]]:
        """从复合字段中提取可用于表格渲染的行数据。"""
        if isinstance(value, list):
            rows = [item for item in value if isinstance(item, dict)]
            return rows
        return []

    @staticmethod
    def _build_composite_metrics(row: dict[str, Any]) -> list[tuple[str, str, Any]]:
        """提取复合结果中的标量指标。"""
        metrics: list[tuple[str, str, Any]] = []
        for key, value in row.items():
            if isinstance(value, (dict, list)):
                if isinstance(value, dict):
                    for child_key, child_value in value.items():
                        if isinstance(child_value, (dict, list)):
                            continue
                        metrics.append((f"{key}.{child_key}", child_key, child_value))
                continue
            metrics.append((key, key, value))
        return metrics

    @staticmethod
    def _infer_composite_summary_field_key(
        row: dict[str, Any],
        metrics: list[tuple[str, str, Any]],
    ) -> str | None:
        """推断复合视图概览区对应的业务字段名。"""

        prefix_candidates = [field_path.split(".", 1)[0] for field_path, _, _ in metrics if "." in field_path]
        if prefix_candidates:
            return prefix_candidates[0]

        for key, value in row.items():
            if isinstance(value, dict):
                return key
        return None

    # ── 指标构建 ──

    @staticmethod
    def _build_metrics(numeric_fields: dict[str, list[float]]) -> list[dict[str, Any]]:
        """为数值字段生成多种聚合指标（sum/avg/count）。

        功能：
            指标卡的目标是快速暴露数据概貌，而不是把所有数值列都塞进页面。这里按分布特征
            选取更有解释价值的合计/均值组合，并控制指标数量上限。

        Edge Cases:
            - 单值列不会重复生成“合计+均值”两张卡，避免信息冗余
            - 指标数量最多保留 4 个，防止摘要区喧宾夺主
        """
        metrics: list[dict[str, Any]] = []
        for column, values in numeric_fields.items():
            if not values:
                continue
            total = sum(values)
            avg = mean(values)
            count = len(values)

            # 根据值的分布选择最有意义的聚合方式
            if count > 1 and total != avg:
                # 有多行数据，展示合计
                metrics.append(
                    {
                        "type": "Metric",
                        "props": {"label": f"{column} (合计)", "value": f"{total:,.2f}", "format": "number"},
                    }
                )
                metrics.append(
                    {
                        "type": "Metric",
                        "props": {"label": f"{column} (均值)", "value": f"{avg:,.2f}", "format": "number"},
                    }
                )
            else:
                metrics.append(
                    {
                        "type": "Metric",
                        "props": {"label": column, "value": f"{total:,.2f}", "format": "number"},
                    }
                )

            if len(metrics) >= 4:
                break
        return metrics

    # ── 图表构建 ──

    def _build_chart(
        self,
        columns: list[str],
        rows: list[dict[str, Any]],
        numeric_fields: dict[str, list[float]],
    ) -> dict[str, Any] | None:
        """从查询结果中推导一个最小可用图表。

        功能：
            图表只作为补充洞察，因此这里坚持“能稳定解释再画”。只有在存在明确分类轴和数值轴时，
            才会生成最小可用图表，避免为了画图而画图。

        Edge Cases:
            - 缺少数值列或分类列时直接返回 `None`，不强行生成误导性图表
            - 数值列里没有任何真实数值时，说明这批数据不适合画图，直接放弃
        """
        if not rows or not numeric_fields:
            return None

        first_numeric = next((col for col in columns if numeric_fields.get(col)), None)
        category_field = next((col for col in columns if col != first_numeric), None)
        if not first_numeric or not category_field:
            return None

        categories = [str(row.get(category_field, "-")) for row in rows]
        values = [row.get(first_numeric) for row in rows]
        if not any(isinstance(v, (int, float)) for v in values):
            return None

        chart_kind = self._detect_chart_type(categories, values, rows)
        option = self._build_chart_option(chart_kind, categories, values, first_numeric)

        return {
            "type": "Chart",
            "props": {
                "title": f"{first_numeric} 分布",
                "kind": chart_kind,
                "option": option,
            },
        }

    @staticmethod
    def _detect_chart_type(
        categories: list[str],
        values: list[Any],
        rows: list[dict[str, Any]],
    ) -> str:
        """根据数据特征自动选择最合适的图表类型。"""
        num_categories = len(set(categories))
        num_rows = len(rows)

        # 类别较少（<=6）且数据行数较少 → 饼图
        if num_categories <= 6 and num_rows <= 10:
            return "pie"

        # 类别是时间序列特征（包含年/月/日/季等关键词） → 折线图
        time_keywords = ["年", "月", "日", "季", "周", "2024", "2025", "2026", "Q1", "Q2", "Q3", "Q4"]
        if any(any(kw in cat for kw in time_keywords) for cat in categories[:3]):
            return "line"

        # 默认柱状图
        return "bar"

    @staticmethod
    def _build_chart_option(
        kind: str,
        categories: list[str],
        values: list[Any],
        series_name: str,
    ) -> dict[str, Any]:
        """根据图表类型生成 ECharts option。

        功能：
            这里统一输出最小可用的 ECharts 配置，保证不同图表类型都沿用同一套标题、图例
            与数据映射口径，方便前端直接透传。

        Edge Cases:
            - 饼图会主动过滤非数值点，避免 ECharts 因脏数据报错
            - 未识别类型时默认回退柱状图，保证始终有稳定配置输出
        """
        if kind == "pie":
            return {
                "tooltip": {"trigger": "item"},
                "legend": {"orient": "vertical", "left": "left"},
                "series": [
                    {
                        "name": series_name,
                        "type": "pie",
                        "radius": "60%",
                        "data": [
                            {"name": cat, "value": val}
                            for cat, val in zip(categories, values)
                            if isinstance(val, (int, float))
                        ],
                    }
                ],
            }

        if kind == "line":
            return {
                "tooltip": {"trigger": "axis"},
                "legend": {"data": [series_name]},
                "xAxis": {"type": "category", "data": categories},
                "yAxis": {"type": "value"},
                "series": [
                    {
                        "name": series_name,
                        "type": "line",
                        "data": values,
                        "smooth": True,
                    }
                ],
            }

        # bar (default)
        return {
            "tooltip": {"trigger": "axis"},
            "legend": {"data": [series_name]},
            "xAxis": {"type": "category", "data": categories},
            "yAxis": {"type": "value"},
            "series": [
                {
                    "name": series_name,
                    "type": "bar",
                    "data": values,
                }
            ],
        }

    @staticmethod
    def _priority_color(priority: str) -> str:
        """把业务优先级映射成前端约定颜色。"""
        priority_value = (priority or "").lower()
        if priority_value in ("urgent", "紧急"):
            return "red"
        if priority_value in ("high", "高"):
            return "volcano"
        if priority_value in ("low", "低"):
            return "blue"
        return "orange"


def _build_runtime_request_fields(
    api_id: str | None,
    *,
    param_source: str | None,
    params: Any,
    flow_num: str | None,
    created_by: str | None,
    request_schema_fields: list[str] | None = None,
) -> dict[str, Any]:
    """构造前端二跳请求所需的统一元数据。

    功能：
        `/api-query` 对外已经不再暴露 `ui_runtime`，因此列表、详情、表单组件必须在
        `ui_spec` 自身携带运行时调用元数据。这里统一输出一套稳定字段，避免不同组件
        自己拼 `api/queryParams/body/flowNum/createdBy` 导致前端读取口径分裂。

    Args:
        api_id: 当前业务接口或 runtime endpoint 的逻辑 ID。
        param_source: 当前接口参数承载位置，`body` 代表非 GET，其他值按 query 处理。
        params: 当前请求参数模板；允许普通对象，也允许包含 `$bindState/$bindRow` 绑定。
        flow_num: 当前链路唯一码；响应层要求与 `trace_id` 保持一致。
        created_by: 已可信任的最终用户标识，来自 `X-User-Id` 解析结果。

    Returns:
        统一元数据字典，始终包含 `api/queryParams/body/flowNum/createdBy` 五个字段。

    Edge Cases:
        - `param_source=body` 时会强制把 queryParams 置空，避免前端二跳出现双通道传参
        - api_id 缺失时 `api` 会回退空串，但其余元数据字段仍保持稳定形状
    """

    return build_request_schema_gated_fields(
        api_id,
        param_source=param_source,
        params=params,
        flow_num=flow_num,
        created_by=created_by,
        allowed_fields=request_schema_fields,
    )


def _build_query_filter_state(runtime: ApiQueryUIRuntime | None) -> dict[str, Any]:
    """构造列表筛选区的初始 state。

    功能：
        筛选表单的输入组件全部依赖 `$bindState`，因此即使某些字段当前为空，也必须在
        `state.filters` 下预留出稳定键位，避免 Guard 把合法输入组件误判为断链。
    """

    if runtime is None:
        return {}

    current_params = dict(runtime.list.query_context.current_params)
    filter_state: dict[str, Any] = {}
    for field in runtime.list.filters.fields:
        filter_state[field.name] = current_params.get(field.name)
    return filter_state


def _build_filter_submit_params(
    runtime: ApiQueryUIRuntime | None,
    filter_fields: list[ApiQueryListFilterFieldRuntime],
) -> dict[str, Any]:
    """构造查询按钮提交参数。

    功能：
        查询按钮的目标不是“只发当前输入框”，而是复用当前列表上下文并覆盖筛选字段。
        这样既能保留分页大小等隐含参数，也能在筛选变化时把页码安全归零到第一页。
    """

    if runtime is None:
        return {}

    next_params = dict(runtime.list.query_context.current_params)
    for field in filter_fields:
        next_params[field.name] = {"$bindState": f"/filters/{field.name}"}

    if runtime.list.query_context.reset_page_on_filter_change:
        page_param = runtime.list.query_context.page_param
        if page_param:
            # 筛选条件变化后回到第一页，避免保留旧页码导致“有条件却无结果”的假空列表。
            next_params[page_param] = 1
    return next_params


def _build_filter_reset_params(
    runtime: ApiQueryUIRuntime | None,
    filter_fields: list[ApiQueryListFilterFieldRuntime],
) -> dict[str, Any]:
    """构造重置按钮提交参数。

    功能：
        重置操作应回到“本页首次渲染时的基线参数”，而不是把所有字段强行清空成 `null`。
        这样能保留上游已经判定为必需的默认值，也避免把 query 参数重置成非法请求。
    """

    del filter_fields
    if runtime is None:
        return {}
    return dict(runtime.list.query_context.current_params)
