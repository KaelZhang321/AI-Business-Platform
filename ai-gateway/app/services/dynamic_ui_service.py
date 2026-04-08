from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from statistics import mean
from typing import Any

from app.core.config import settings
from app.models.schemas import ApiQueryExecutionStatus, ApiQueryUIRuntime, KnowledgeResult
from app.services.ui_catalog_service import UICatalogService
from app.services.ui_spec_guard import UISpecGuard, UISpecValidationResult

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
    validation: UISpecValidationResult = field(default_factory=UISpecValidationResult)
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
        """生成待 Guard 校验的候选 Spec。"""
        execution_status = ApiQueryExecutionStatus(status) if status else None

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
        """
        if runtime is None:
            return {"mode": "read_only", "components": []}

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

        json_text = self._extract_json_object(raw_reply)
        if not json_text:
            return None

        try:
            parsed = json.loads(json_text)
        except json.JSONDecodeError:
            logger.debug("Failed to parse renderer json: %s", raw_reply[:200])
            return None

        return parsed if isinstance(parsed, dict) else None

    def _extract_json_object(self, raw_reply: str) -> str:
        """从模型输出中剥离首个 JSON 对象文本。

        功能：
            这里复用第二阶段的脏 JSON 清洗思路，但保持在第五阶段本地闭环，避免跨模块
            直接依赖私有 helper。这样做虽然有少量重复代码，但能保持渲染链路独立可演进。
        """
        text = raw_reply.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or start >= end:
            return ""

        json_text = text[start : end + 1]
        json_text = self._strip_json_comments(json_text)
        json_text = self._strip_trailing_commas(json_text)
        return json_text

    @staticmethod
    def _strip_json_comments(text: str) -> str:
        """删除 JSON 中的注释，同时保留字符串字面量原文。"""
        result: list[str] = []
        index = 0
        in_string = False
        escaped = False
        length = len(text)

        while index < length:
            char = text[index]
            next_char = text[index + 1] if index + 1 < length else ""

            if in_string:
                result.append(char)
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                index += 1
                continue

            if char == '"':
                in_string = True
                result.append(char)
                index += 1
                continue

            if char == "/" and next_char == "/":
                index += 2
                while index < length and text[index] not in ("\n", "\r"):
                    index += 1
                continue

            if char == "/" and next_char == "*":
                index += 2
                while index + 1 < length and not (text[index] == "*" and text[index + 1] == "/"):
                    index += 1
                index += 2
                continue

            result.append(char)
            index += 1

        return "".join(result)

    @staticmethod
    def _strip_trailing_commas(text: str) -> str:
        """删除对象和数组闭合前的尾逗号。"""
        result: list[str] = []
        index = 0
        in_string = False
        escaped = False
        length = len(text)

        while index < length:
            char = text[index]

            if in_string:
                result.append(char)
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                index += 1
                continue

            if char == '"':
                in_string = True
                result.append(char)
                index += 1
                continue

            if char == ",":
                lookahead = index + 1
                while lookahead < length and text[lookahead].isspace():
                    lookahead += 1
                if lookahead < length and text[lookahead] in ("]", "}"):
                    index += 1
                    continue

            result.append(char)
            index += 1

        return "".join(result)

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
        """把知识检索结果渲染成列表卡片。"""
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
        render_mode = (context or {}).get("query_render_mode") or "table"
        root_props = {
            "title": (context or {}).get("question", "数据查询结果"),
            "subtitle": self._build_query_subtitle(rows, context, render_mode),
        }
        children: list[dict[str, Any]] = []

        if include_partial_notice:
            children.append(
                {
                    "type": "PlannerNotice",
                    "props": {
                        "text": (context or {}).get("partial_message", "部分步骤执行失败，当前仅展示成功返回的数据。"),
                        "tone": "info",
                    },
                }
            )

        if render_mode == "detail":
            children.append(
                {
                    "type": "PlannerDetailCard",
                    "props": {
                        "title": (context or {}).get("detail_title", "详情信息"),
                        "items": self._build_detail_items(rows[0]),
                    },
                }
            )
            return self._build_flat_card_spec(root_props=root_props, children=children)

        table_props: dict[str, Any] = {
            "columns": self._build_table_columns(rows[0]),
            "dataSource": rows,
        }
        if runtime and runtime.detail.enabled:
            # 详情动作只下发运行时契约，不在网关 UI 层硬编码具体业务参数。
            table_props["rowActions"] = [
                {
                    "type": runtime.detail.ui_action or "remoteQuery",
                    "label": "查看详情",
                    "params": {
                        "api_id": runtime.detail.api_id,
                        "route_url": runtime.detail.route_url,
                        "request": runtime.detail.request.model_dump(exclude_none=True),
                        "source": runtime.detail.source.model_dump(exclude_none=True),
                    },
                }
            ]
        if runtime and runtime.list.pagination.enabled:
            # 分页后续走 remoteQuery + mutation_target 做局部补丁，不重新生成整页 UI。
            table_props["pagination"] = {
                "enabled": True,
                "total": runtime.list.pagination.total,
                "currentPage": runtime.list.pagination.current_page,
                "pageSize": runtime.list.pagination.page_size,
                "action": {
                    "type": runtime.list.ui_action or "remoteQuery",
                    "params": {
                        "api_id": runtime.list.api_id,
                        "route_url": runtime.list.route_url,
                        "response_mode": "patch",
                        "param_source": runtime.list.param_source,
                        "pagination": runtime.list.pagination.model_dump(exclude_none=True),
                        "filters": runtime.list.filters.model_dump(exclude_none=True),
                        "query_context": runtime.list.query_context.model_dump(exclude_none=True),
                        "patch_context": {
                            "patch_type": "list_query",
                            "trigger": "pagination",
                            "mutation_target": runtime.list.pagination.mutation_target,
                        },
                        "mutation_target": runtime.list.pagination.mutation_target,
                    },
                },
            }

        children.append({"type": "PlannerTable", "props": table_props})
        return self._build_flat_card_spec(root_props=root_props, children=children)

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
        """将待办列表渲染成带筛选器的工作台视图。"""
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
    def _build_table_columns(sample_row: dict[str, Any]) -> list[dict[str, str]]:
        """把行对象字段映射成 `PlannerTable.columns`。

        功能：
            这里输出稳定的列元数据而不是裸字符串，是为了给后续前端表格实现预留
            `title / dataIndex / key` 三元组契约，避免任务 2 做完后任务 5 又得返工改列结构。
        """
        return [
            {
                "key": key,
                "title": key,
                "dataIndex": key,
            }
            for key in sample_row.keys()
        ]

    @staticmethod
    def _build_detail_items(row: dict[str, Any]) -> list[dict[str, str]]:
        """把对象详情映射成 `PlannerDetailCard.items`。

        功能：
            详情视图的目标是“稳定展示事实”，不是透传原始对象结构。
            因此这里统一把值折叠成可读字符串，避免复杂嵌套对象直接把详情卡 props 撑穿。
        """
        return [
            {
                "label": key,
                "value": DynamicUIService._stringify_detail_value(value),
            }
            for key, value in row.items()
        ]

    @staticmethod
    def _stringify_detail_value(value: Any) -> str:
        """将详情值折叠为可展示文本。"""
        if value is None:
            return "-"
        if isinstance(value, bool):
            return "是" if value else "否"
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, str):
            return value
        return str(value)

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
        if render_mode == "summary_table":
            return f"当前展示 {len(rows)} 个执行步骤的汇总结果"
        if isinstance(total, int) and total > len(rows):
            return f"共 {total} 条，当前展示 {len(rows)} 条"
        return f"当前展示 {len(rows)} 条"

    # ── 指标构建 ──

    @staticmethod
    def _build_metrics(numeric_fields: dict[str, list[float]]) -> list[dict[str, Any]]:
        """为数值字段生成多种聚合指标（sum/avg/count）。"""
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
        """从查询结果中推导一个最小可用图表。"""
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
        """根据图表类型生成 ECharts option。"""
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
