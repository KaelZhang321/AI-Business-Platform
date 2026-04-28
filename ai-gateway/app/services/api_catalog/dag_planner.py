"""第三阶段 DAG Planner。

功能：
    把第二阶段召回出的候选查询接口进一步编排成 DAG 计划，并在落地执行前
    完成白名单、环依赖和 JSONPath 引用的强校验。

设计动机：
    第三阶段最怕的不是“规划得不够聪明”，而是“规划了一张错误图纸还继续执行”。
    因此这里把 Planner 设计成两段式：

    1. 让 LLM 负责生成草稿图纸
    2. 让网关代码负责做不可妥协的结构校验
"""

from __future__ import annotations

import json
import logging
from graphlib import CycleError, TopologicalSorter
from typing import Any

from pydantic import ValidationError

from app.core.config import settings
from app.models.schemas import ApiQueryExecutionPlan, ApiQueryPlanStep, ApiQueryRoutingResult
from app.services.api_catalog.dag_bindings import (
    DagBindingSyntaxError,
    collect_binding_step_ids,
    is_dag_binding,
    parse_binding_expression,
)
from app.services.api_catalog.graph_models import ApiCatalogSubgraphResult
from app.services.api_catalog.graph_plan_validator import GraphPlanValidationError, GraphPlanValidator
from app.services.api_catalog.schema import (
    ApiCatalogEntry,
    ApiCatalogPredecessorSpec,
    ApiCatalogSearchResult,
)
from app.utils.json_utils import parse_dirty_json_object, summarize_log_text

logger = logging.getLogger(__name__)
_QUERY_SAFE_METHODS = {"GET", "POST"}
_PREDECESSOR_SELECT_MODE_TO_BINDING_TEMPLATE = {
    "single": "$[{step_id}.data].{source_path}",
    "first": "$[{step_id}.data].{source_path}",
    "all": "$[{step_id}.data][*].{source_path}",
    "user_select": "$[{step_id}.data][*].{source_path}",
}


class DagPlanValidationError(ValueError):
    """第三阶段 DAG 校验失败。"""

    def __init__(self, code: str, message: str, metadata: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.metadata = metadata or {}


class ApiDagPlanner:
    """第三阶段查询 DAG 规划器。

    功能：
        基于用户问题、阶段二召回候选和路由提示，输出只包含查询安全接口的执行计划。

    Returns:
        `ApiQueryExecutionPlan`，后续仍需经过白名单与环检测才能进入执行器。

    Edge Cases:
        - LLM 不返回合法 JSON 时，会抛出结构化校验异常，由 route 层统一降级
        - 任意一步引用候选集外接口、未声明依赖或形成环，都会被直接拦截
    """

    def __init__(self, llm_service: Any | None = None, graph_plan_validator: GraphPlanValidator | None = None) -> None:
        """初始化第三阶段 DAG Planner。

        Args:
            llm_service: 可选的 LLM 调用服务。

        功能：
            第三阶段最看重的是图纸稳定性，因此允许由外层把 `/api_query` 专用模型显式
            注入进来，避免 Planner 在不同运行环境里命中不同默认后端。
        """
        self._llm = llm_service
        self._graph_plan_validator = graph_plan_validator or GraphPlanValidator()

    def _get_llm(self):
        """懒加载 LLM 服务，避免单接口直达路径也初始化 Planner 客户端。"""
        if self._llm is None:
            from app.services.llm_service import LLMService

            self._llm = LLMService()
        return self._llm

    async def build_plan(
        self,
        query: str,
        candidates: list[ApiCatalogSearchResult],
        user_context: dict[str, Any] | None,
        route_hint: ApiQueryRoutingResult,
        predecessor_hints: dict[str, list[ApiCatalogPredecessorSpec]] | None = None,
        *,
        trace_id: str | None = None,
    ) -> ApiQueryExecutionPlan:
        """调用 LLM 生成第三阶段 DAG 草稿。

        Args:
            query: 用户自然语言请求。
            candidates: 第二阶段召回出的候选接口列表。
            user_context: 用户上下文，主要用于主语补全和组织信息提示。
            route_hint: 第二阶段轻量路由结果，帮助 Planner 理解业务域边界。

        Returns:
            经过 Pydantic 结构校验的 `ApiQueryExecutionPlan`。

        Raises:
            DagPlanValidationError: 当 LLM 返回为空或 JSON 结构非法时抛出。

        Edge Cases:
            - 候选集为空时不触发 Planner，直接抛出校验错误
            - 即使 JSON Mode 成功，仍要用模型校验拦截脏字段和缺字段
        """
        if not candidates:
            raise DagPlanValidationError("planner_candidates_empty", "缺少可规划的候选接口。")

        prompt = _build_planner_prompt(
            query,
            candidates,
            user_context,
            route_hint,
            predecessor_hints=predecessor_hints,
        )
        raw_payload = await self._call_llm_json(prompt, trace_id=trace_id)
        if not raw_payload:
            logger.warning(
                "stage3 planner degraded trace_id=%s code=%s query=%s",
                trace_id or "-",
                "planner_parse_failed",
                summarize_log_text(query),
            )
            raise DagPlanValidationError("planner_parse_failed", "Planner 未返回可解析的 DAG JSON。")

        try:
            plan = ApiQueryExecutionPlan.model_validate(raw_payload)
        except ValidationError as exc:
            raise DagPlanValidationError("planner_schema_invalid", f"Planner DAG 结构非法: {exc}") from exc

        if not plan.steps:
            raise DagPlanValidationError("planner_steps_empty", "Planner 未规划出任何执行步骤。")

        return plan

    def validate_plan(
        self,
        plan: ApiQueryExecutionPlan,
        candidates: list[ApiCatalogSearchResult],
        predecessor_hints: dict[str, list[ApiCatalogPredecessorSpec]] | None = None,
        *,
        subgraph_result: ApiCatalogSubgraphResult | None = None,
        trace_id: str | None = None,
    ) -> dict[str, ApiCatalogEntry]:
        """对查询 DAG 做结构、白名单与图事实校验。

        Args:
            plan: Planner 生成的 DAG。
            candidates: 第二阶段召回出的候选接口。

        Returns:
            `step_id -> ApiCatalogEntry` 的映射，供执行阶段直接使用。

        Raises:
            DagPlanValidationError: DAG 命中未知接口、依赖非法或形成环时抛出。

        Edge Cases:
            - 同一路径允许被多个步骤复用，但每个步骤 ID 必须唯一
            - JSONPath 引用到未声明依赖时直接拦截，避免执行阶段出现隐式依赖
            - 子图可用时，会追加字段路径与基数对齐校验，把危险误编排拦在 Stage 3
        """
        allowed_entries_by_id = _build_allowed_entries_by_id(candidates)
        allowed_entries_by_path = _build_allowed_entries_by_path(candidates)
        plan_steps_by_id = {step.step_id: step for step in plan.steps}
        step_entries: dict[str, ApiCatalogEntry] = {}

        if len(plan_steps_by_id) != len(plan.steps):
            raise DagPlanValidationError("planner_duplicate_step_id", "Planner 生成了重复的 step_id。")

        for step in plan.steps:
            entry = _resolve_allowed_entry(step, allowed_entries_by_id, allowed_entries_by_path)
            if entry is None:
                raise DagPlanValidationError(
                    "planner_unknown_api",
                    f"Planner 引用了候选集外接口: {step.api_id or step.api_path}",
                )

            if step.api_id and entry.id != step.api_id:
                raise DagPlanValidationError(
                    "planner_api_id_mismatch",
                    f"步骤 {step.step_id} 的 api_id 与 api_path 不匹配: {step.api_id} != {entry.id}",
                )

            if entry.operation_safety == "mutation":
                raise DagPlanValidationError(
                    "planner_unsafe_api",
                    f"Planner 引入了非查询语义接口: {entry.id}",
                )

            if entry.method not in _QUERY_SAFE_METHODS:
                raise DagPlanValidationError(
                    "planner_method_not_allowed",
                    f"Planner 引入了不允许的接口方法: {entry.method} {entry.path}",
                )

            missing_dependencies = [dep for dep in step.depends_on if dep not in plan_steps_by_id]
            if missing_dependencies:
                raise DagPlanValidationError(
                    "planner_missing_dependency",
                    f"步骤 {step.step_id} 依赖了不存在的前置步骤: {missing_dependencies}",
                )

            step_entries[step.step_id] = entry

        rewritten_binding_count, appended_dependency_count = _enforce_required_predecessor_bindings(
            plan,
            step_entries=step_entries,
            predecessor_hints=predecessor_hints or {},
        )
        if rewritten_binding_count > 0 or appended_dependency_count > 0:
            logger.info(
                (
                    "stage3 planner predecessor contract enforced trace_id=%s "
                    "rewritten_bindings=%s appended_dependencies=%s"
                ),
                trace_id or "-",
                rewritten_binding_count,
                appended_dependency_count,
            )

        for step in plan.steps:
            normalized_binding_count = _normalize_zero_index_bindings_in_step_params(step)
            semantic_fix_count = _normalize_redundant_data_prefix_bindings_in_step_params(step)
            if normalized_binding_count > 0 or semantic_fix_count > 0:
                logger.info(
                    (
                        "stage3 planner binding normalized trace_id=%s step_id=%s "
                        "normalized_count=%s semantic_fix_count=%s"
                    ),
                    trace_id or "-",
                    step.step_id,
                    normalized_binding_count,
                    semantic_fix_count,
                )

            try:
                binding_dependencies = collect_binding_step_ids(step.params)
            except DagBindingSyntaxError as exc:
                raise DagPlanValidationError(
                    "planner_binding_syntax_invalid",
                    f"步骤 {step.step_id} 的 JSONPath 绑定语法非法: {exc}",
                ) from exc

            undeclared_dependencies = sorted(binding_dependencies.difference(step.depends_on))
            if undeclared_dependencies:
                raise DagPlanValidationError(
                    "planner_undeclared_dependency",
                    f"步骤 {step.step_id} 引用了未在 depends_on 中声明的上游步骤: {undeclared_dependencies}",
                )

        _validate_required_predecessors(
            plan,
            step_entries=step_entries,
            predecessor_hints=predecessor_hints or {},
        )

        dependency_graph = {step.step_id: set(step.depends_on) for step in plan.steps}

        try:
            tuple(TopologicalSorter(dependency_graph).static_order())
        except CycleError as exc:
            raise DagPlanValidationError("planner_cycle_detected", "Planner 生成的 DAG 存在循环依赖。") from exc

        if settings.api_catalog_graph_validation_enabled:
            try:
                self._graph_plan_validator.validate_plan(
                    plan=plan,
                    step_entries=step_entries,
                    subgraph_result=subgraph_result,
                )
            except GraphPlanValidationError as exc:
                raise DagPlanValidationError(exc.code, exc.message, metadata=exc.metadata) from exc

        return step_entries

    async def _call_llm_json(self, prompt: str, *, trace_id: str | None = None) -> dict[str, Any]:
        """调用 Planner 大模型并尽量提取合法 JSON。

        功能：
            第三阶段图纸结构比第二阶段更复杂，因此先启用 JSON Mode，再保留一次
            纯文本重试，避免兼容后端不支持 `response_format` 时整条链路直接失效。

        Returns:
            解析出的 JSON 对象；失败时返回空字典。
        """
        llm = self._get_llm()
        max_attempts = max(1, settings.api_query_route_retry_count + 1)

        for attempt in range(max_attempts):
            use_json_mode = attempt == 0
            try:
                raw = await llm.chat(
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.0,
                    response_format={"type": "json_object"} if use_json_mode else None,
                    timeout_seconds=settings.api_query_route_timeout_seconds,
                )
            except Exception as exc:
                logger.warning(
                    "Planner LLM call failed trace_id=%s on attempt %s/%s: %s",
                    trace_id or "-",
                    attempt + 1,
                    max_attempts,
                    exc,
                )
                continue

            parsed = parse_dirty_json_object(raw)
            if parsed:
                return parsed

            logger.warning(
                "Planner LLM returned non-json payload trace_id=%s on attempt %s/%s raw=%s",
                trace_id or "-",
                attempt + 1,
                max_attempts,
                summarize_log_text(raw),
            )

        return {}


def build_single_step_plan(
    entry: ApiCatalogEntry,
    params: dict[str, Any],
    *,
    step_id: str,
    plan_id: str,
) -> ApiQueryExecutionPlan:
    """为单候选命中场景构造确定性执行计划。

    功能：
        当前系统仍需要兼容“只有一个候选接口”的高频查询。如果此时也强制走 Planner，
        反而会把稳定的直达链路暴露给不必要的模型波动。

    Returns:
        只包含一个查询安全步骤的执行计划。
    """
    return ApiQueryExecutionPlan(
        plan_id=plan_id,
        steps=[
            ApiQueryPlanStep(
                step_id=step_id,
                api_id=entry.id,
                api_path=entry.path,
                params=dict(params),
                depends_on=[],
            )
        ],
    )


def _build_allowed_entries_by_path(candidates: list[ApiCatalogSearchResult]) -> dict[str, ApiCatalogEntry]:
    """按路径整理候选接口，作为第三阶段白名单来源。"""
    allowed_entries: dict[str, ApiCatalogEntry] = {}
    allowed_entries_by_id = _build_allowed_entries_by_id(candidates)
    for entry in allowed_entries_by_id.values():
        # 这里故意保留“第一次命中的条目”，因为候选集已经按召回顺序排好，
        # 后续校验阶段只需要知道某条路径是否合法，不需要再次重排。
        allowed_entries.setdefault(entry.path, entry)
    return allowed_entries


def _build_allowed_entries_by_id(candidates: list[ApiCatalogSearchResult]) -> dict[str, ApiCatalogEntry]:
    """按接口 ID 整理候选接口，并把伴生接口解析为 `ApiCatalogEntry` 后并入白名单。"""
    allowed_entries: dict[str, ApiCatalogEntry] = {}

    for candidate in candidates:
        if candidate.entry.id not in allowed_entries:
            allowed_entries[candidate.entry.id] = candidate.entry
        for predecessor in candidate.entry.predecessors:
            if isinstance(predecessor, ApiCatalogEntry) and predecessor.id not in allowed_entries:
                allowed_entries[predecessor.id] = predecessor
    return allowed_entries


def _resolve_predecessor_entries(
    entry: ApiCatalogEntry,
    entries_by_id: dict[str, ApiCatalogEntry],
) -> list[ApiCatalogEntry]:
    """把伴生 predecessor 解析为可直接使用的 `ApiCatalogEntry` 列表。

    功能：
        兼容两类 predecessor 载荷：
        1) 旧形态：`ApiCatalogPredecessorSpec`（仅包含 predecessor_api_id）
        2) 新形态：`ApiCatalogEntry`（已是完整伴生接口对象）
    """
    predecessor_entries: list[ApiCatalogEntry] = []
    for predecessor in entry.predecessors:
        if isinstance(predecessor, ApiCatalogEntry):
            predecessor_entries.append(predecessor)
            continue
        predecessor_api_id = getattr(predecessor, "predecessor_api_id", None)
        if not predecessor_api_id:
            continue
        predecessor_entry = entries_by_id.get(str(predecessor_api_id))
        if predecessor_entry is not None:
            predecessor_entries.append(predecessor_entry)
    return predecessor_entries


def _resolve_allowed_entry(
    step: ApiQueryPlanStep,
    allowed_entries_by_id: dict[str, ApiCatalogEntry],
    allowed_entries_by_path: dict[str, ApiCatalogEntry],
) -> ApiCatalogEntry | None:
    """优先按 `api_id`，再按 `api_path` 命中白名单条目。

    功能：
        引入 POST 查询接口后，同一路径下可能同时存在 GET/POST 两个目录项。Planner 如果
        只回 `api_path`，校验层就无法稳定判断它到底想调用哪一条接口，因此这里优先消费
        `api_id`；只有兼容历史图纸时才回退到 `api_path`。
    """
    if step.api_id:
        entry = allowed_entries_by_id.get(step.api_id)
        if entry is not None:
            return entry
    return allowed_entries_by_path.get(step.api_path)


def _build_planner_prompt(
    query: str,
    candidates: list[ApiCatalogSearchResult],
    user_context: dict[str, Any] | None,
    route_hint: ApiQueryRoutingResult,
    predecessor_hints: dict[str, list[ApiCatalogPredecessorSpec]] | None = None,
) -> str:
    """构建第三阶段 Planner 提示词。"""
    context_str = json.dumps(user_context or {}, ensure_ascii=False)
    route_hint_payload = {
        "query_domains": list(route_hint.query_domains),
        "business_intents": list(route_hint.business_intents),
        "is_multi_domain": route_hint.is_multi_domain,
        "reasoning": route_hint.reasoning,
    }
    candidate_lines = []
    for index, candidate in enumerate(candidates, start=1):
        entry = candidate.entry
        request_schema = json.dumps(entry.param_schema.model_dump(), ensure_ascii=False)
        candidate_lines.append(
            f"{index}. `{entry.method} {entry.path}`\n"
            f"   - api_id: {entry.id}\n"
            f"   - operation_safety: {entry.operation_safety}\n"
            f"   - domain: {entry.domain}\n"
            f"   - description: {entry.description}\n"
            f"   - request_schema: {request_schema}\n"
            f"   - response_data_path: {entry.response_data_path}"
        )

    candidate_block = "\n".join(candidate_lines)
    predecessor_hints_payload = _build_predecessor_hints_payload(predecessor_hints or {})
    return f"""# Role
    你是一个企业级 API 工作流编排引擎 (Planner)。
    你的任务是：根据用户的自然语言请求，以及系统提供的[Available APIs]，编排出一个高效的 API 调用执行计划 (DAG)。
    
    # Definitions (系统概念定义)
    1. **Predecessor Hints (上游依赖提示)**: 系统会提供部分 API 的强依赖关系。格式为：`{{"目标_api_id": [依赖说明对象]}}`。
       - `predecessor_api_id`: 目标 API 必须依赖的上游 API ID。
       - `required`: 如果为 True，则必须先调用该上游 API。
       - `param_bindings`: 描述数据流转规则。
         - `target_param`: 目标 API 需要的入参名。
         - `source_path`: 从上游 API 响应中提取数据的 JSONPath (如 `$.result.items[*].idCardObfuscated`)。
    
    # Execution Rules (安全红线 - 必须绝对遵守)
    1. 绝对禁止使用 `operation_safety != query` 的接口。
    2. 你只能使用以下 `operation_safety=query` 且 `method in [GET, POST]` 的接口来拉取数据。
    3. 你不能编造 API 路径、参数名或步骤 ID。
    
    # Execution Rules (编排与推断规则)
    1. **最小化调用**：只调用对回答用户问题有帮助的 API。
    2. **并发优先**：如果多个 API 没有数据依赖，`depends_on` 必须为空数组。
    3. **显式依赖优先 (Hard Constraints)**：
       - 如果你要使用的目标 API 在 [Companion Predecessor Hints] 中存在记录，且 `required=True`，你**必须**在计划中先编排其对应的 `predecessor_api_id` 步骤。
       - 目标步骤必须在 `depends_on` 中显式包含上游步骤的 `step_id`。
       - 目标步骤的 `params` 必须根据提示中的 `target_param` 和 `source_path` 建立参数绑定。
    4. **隐式依赖推断 (Soft Inference)**：
       - 如果某个 API 需要必填参数（如 `user_id`），但 [Companion Predecessor Hints] 中**没有**关于该 API 的说明。
       - 你必须发挥推理能力，从同计划的其他 API 返回值中寻找能提供该参数的接口，建立依赖关系，并自己构造合法的 JSONPath 进行绑定。
    5. **参数传递语法**：
       - 动态引用上游步骤数据的固定语法前缀为：`$[step_id.data]`，后面拼接标准的 JSONPath。
       - 示例（提取单值）：`$[step_id.data].result.id`
       - 示例（提取数组）：`$[step_id.data].result.items[*].idCardObfuscated`
    6. 所有步骤的 `step_id` 必须唯一，且只使用字母、数字、下划线。
    
    # Output Format
    必须返回合法的纯 JSON 格式，不包含任何 Markdown 标记。结构如下：
    {{
      "plan_id": "dag_xxx",
      "steps": [
        {{
          "step_id": "step_1",
          "api_id": "endpoint_xxx",
          "api_path": "/api/xxx",
          "params": {{"静态参数": "value", "动态参数": "$[上游step_id.data].path..."}},
          "depends_on": []
        }}
      ]
    }}
    
    # Example
    如果用户想“先查客户，再根据客户 ID 查订单”：
    {{
      "plan_id": "dag_customer_orders",
      "steps": [
        {{
          "step_id": "step_customers",
          "api_id": "customer_list",
          "api_path": "/api/crm/customers",
          "params": {{"owner_id": "E8899"}},
          "depends_on": []
        }},
        {{
          "step_id": "step_orders",
          "api_id": "order_stats",
          "api_path": "/api/orders/stats",
          "params": {{"customer_ids": "$[step_customers.data].result.items[*].id"}},
          "depends_on": ["step_customers"]
        }}
      ]
    }}
    
    =========================================
    # Context & Inputs (本次任务输入)
    
    【User Query】: {query}
    【User Context】: {context_str}
    【Routing Hints】: {json.dumps(route_hint_payload, ensure_ascii=False)}
    
    【Available APIs】
    {candidate_block}
    
    【Companion Predecessor Hints】
    {json.dumps(predecessor_hints_payload, ensure_ascii=False)}
    """


def _build_predecessor_hints_payload(
    predecessor_hints: dict[str, list[ApiCatalogPredecessorSpec]],
) -> dict[str, list[dict[str, Any]]]:
    """将 predecessor 规则压缩为 prompt 可读的结构化提示。"""
    payload: dict[str, list[dict[str, Any]]] = {}
    for target_api_id, specs in predecessor_hints.items():
        if not specs:
            continue
        payload[target_api_id] = [
            {
                "predecessor_api_id": spec.predecessor_api_id,
                "required": spec.required,
                "order": spec.order,
                "param_bindings": [
                    {
                        "target_param": binding.target_param,
                        "source_path": binding.source_path,
                        "select_mode": binding.select_mode,
                    }
                    for binding in spec.param_bindings
                ],
            }
            for spec in specs
        ]
    return payload


def _normalize_zero_index_bindings_in_step_params(step: ApiQueryPlanStep) -> int:
    """把绑定表达式中的 `[0]` 归一化为受限语法可接受形式。"""
    normalized_params, normalized_count = _normalize_zero_index_bindings(step.params)
    if normalized_count > 0:
        step.params = normalized_params
    return normalized_count


def _normalize_zero_index_bindings(payload: Any) -> tuple[Any, int]:
    """递归归一化参数载荷中的绑定表达式。"""
    if isinstance(payload, dict):
        normalized_payload: dict[str, Any] = {}
        total = 0
        for key, value in payload.items():
            normalized_value, count = _normalize_zero_index_bindings(value)
            normalized_payload[key] = normalized_value
            total += count
        return normalized_payload, total

    if isinstance(payload, list):
        normalized_items: list[Any] = []
        total = 0
        for item in payload:
            normalized_item, count = _normalize_zero_index_bindings(item)
            normalized_items.append(normalized_item)
            total += count
        return normalized_items, total

    if isinstance(payload, str) and is_dag_binding(payload):
        normalized = payload.replace("[0]", "")
        if normalized != payload:
            return normalized, 1

    return payload, 0


def _normalize_redundant_data_prefix_bindings_in_step_params(step: ApiQueryPlanStep) -> int:
    """移除绑定表达式在 `step.data` 之后的冗余 `.data` 前缀。"""
    normalized_params, normalized_count = _normalize_redundant_data_prefix_bindings(step.params)
    if normalized_count > 0:
        step.params = normalized_params
    return normalized_count


def _normalize_redundant_data_prefix_bindings(payload: Any) -> tuple[Any, int]:
    """递归归一化参数载荷中的冗余 `.data` 绑定语义。"""
    if isinstance(payload, dict):
        normalized_payload: dict[str, Any] = {}
        total = 0
        for key, value in payload.items():
            normalized_value, count = _normalize_redundant_data_prefix_bindings(value)
            normalized_payload[key] = normalized_value
            total += count
        return normalized_payload, total

    if isinstance(payload, list):
        normalized_items: list[Any] = []
        total = 0
        for item in payload:
            normalized_item, count = _normalize_redundant_data_prefix_bindings(item)
            normalized_items.append(normalized_item)
            total += count
        return normalized_items, total

    if isinstance(payload, str) and is_dag_binding(payload):
        try:
            parsed = parse_binding_expression(payload)
        except DagBindingSyntaxError:
            return payload, 0
        tokens = list(parsed.tokens)
        if not tokens or tokens[0] != ".data":
            return payload, 0
        while tokens and tokens[0] == ".data":
            tokens.pop(0)
        normalized = f"$[{parsed.step_id}.data]{''.join(tokens)}"
        return normalized, 1

    return payload, 0


def _normalize_predecessor_source_path(source_path: str, *, response_data_path: str) -> str:
    """把 predecessor source_path 转换为绑定表达式可消费格式。"""
    raw = str(source_path or "").strip()
    if not raw:
        return ""
    raw = raw.removeprefix("$").lstrip(".").replace("[]", "[*]")
    normalized_response_data_path = (
        str(response_data_path or "").strip().removeprefix("$").lstrip(".").replace("[]", "[*]")
    )

    for prefix in (normalized_response_data_path, "data"):
        stripped = _strip_predecessor_source_prefix(raw, prefix)
        if stripped is not None:
            raw = stripped
            break

    raw = raw.lstrip(".")
    if raw.startswith("[*]."):
        raw = raw[len("[*].") :]
    elif raw == "[*]":
        return ""
    return raw


def _strip_predecessor_source_prefix(path: str, prefix: str) -> str | None:
    """剥离 source_path 中的上游响应根前缀。"""
    normalized_prefix = str(prefix or "").strip().removeprefix("$").lstrip(".").replace("[]", "[*]")
    if not normalized_prefix:
        return None

    if path == normalized_prefix or path == f"{normalized_prefix}[*]":
        return ""

    dotted_prefix = f"{normalized_prefix}."
    if path.startswith(dotted_prefix):
        return path[len(dotted_prefix) :]

    wildcard_prefix = f"{normalized_prefix}[*]."
    if path.startswith(wildcard_prefix):
        return path[len(wildcard_prefix) :]

    return None


def _build_predecessor_binding_expression(*, step_id: str, source_path: str, select_mode: str) -> str:
    """构造受限 DAG 绑定表达式。"""
    normalized_mode = select_mode if select_mode in _PREDECESSOR_SELECT_MODE_TO_BINDING_TEMPLATE else "single"
    template = _PREDECESSOR_SELECT_MODE_TO_BINDING_TEMPLATE[normalized_mode]
    return template.format(step_id=step_id, source_path=source_path)


def _enforce_required_predecessor_bindings(
    plan: ApiQueryExecutionPlan,
    *,
    step_entries: dict[str, ApiCatalogEntry],
    predecessor_hints: dict[str, list[ApiCatalogPredecessorSpec]],
) -> tuple[int, int]:
    """根据 required predecessor 合同覆盖绑定并补齐依赖。"""
    if not predecessor_hints:
        return 0, 0

    step_id_by_api_id: dict[str, str] = {}
    for step in plan.steps:
        entry = step_entries.get(step.step_id)
        if entry is None:
            continue
        step_id_by_api_id.setdefault(entry.id, step.step_id)

    rewritten_binding_count = 0
    appended_dependency_count = 0
    for step in plan.steps:
        entry = step_entries.get(step.step_id)
        if entry is None:
            continue
        required_specs = [spec for spec in predecessor_hints.get(entry.id, []) if spec.required]
        if not required_specs:
            continue

        params = dict(step.params)
        depends_on = list(step.depends_on)
        for required_spec in required_specs:
            predecessor_step_id = step_id_by_api_id.get(required_spec.predecessor_api_id)
            if predecessor_step_id is None:
                continue
            if predecessor_step_id not in depends_on:
                depends_on.append(predecessor_step_id)
                appended_dependency_count += 1
            predecessor_entry = step_entries.get(predecessor_step_id)
            response_data_path = predecessor_entry.response_data_path if predecessor_entry is not None else "data"
            for binding in required_spec.param_bindings:
                source_path = _normalize_predecessor_source_path(
                    binding.source_path,
                    response_data_path=response_data_path,
                )
                if not source_path:
                    continue
                expected_expression = _build_predecessor_binding_expression(
                    step_id=predecessor_step_id,
                    source_path=source_path,
                    select_mode=binding.select_mode,
                )
                if params.get(binding.target_param) != expected_expression:
                    params[binding.target_param] = expected_expression
                    rewritten_binding_count += 1

        step.params = params
        step.depends_on = depends_on

    return rewritten_binding_count, appended_dependency_count


def _validate_required_predecessors(
    plan: ApiQueryExecutionPlan,
    *,
    step_entries: dict[str, ApiCatalogEntry],
    predecessor_hints: dict[str, list[ApiCatalogPredecessorSpec]],
) -> None:
    """校验 required predecessor 在计划中的存在、依赖与绑定完整性。"""
    if not predecessor_hints:
        return

    step_id_by_api_id: dict[str, str] = {}
    for step in plan.steps:
        entry = step_entries.get(step.step_id)
        if entry is None:
            continue
        step_id_by_api_id.setdefault(entry.id, step.step_id)

    for step in plan.steps:
        entry = step_entries.get(step.step_id)
        if entry is None:
            continue
        required_specs = [spec for spec in predecessor_hints.get(entry.id, []) if spec.required]
        if not required_specs:
            continue

        for required_spec in required_specs:
            predecessor_step_id = step_id_by_api_id.get(required_spec.predecessor_api_id)
            if predecessor_step_id is None:
                raise DagPlanValidationError(
                    "planner_missing_required_predecessor",
                    f"步骤 {step.step_id} 缺少 required predecessor: {required_spec.predecessor_api_id}",
                    metadata={
                        "target_api_id": entry.id,
                        "target_step_id": step.step_id,
                        "required_predecessor_api_id": required_spec.predecessor_api_id,
                    },
                )
            if predecessor_step_id not in step.depends_on:
                raise DagPlanValidationError(
                    "planner_missing_required_predecessor",
                    f"步骤 {step.step_id} 未声明 required predecessor 依赖: {required_spec.predecessor_api_id}",
                    metadata={
                        "target_api_id": entry.id,
                        "target_step_id": step.step_id,
                        "required_predecessor_api_id": required_spec.predecessor_api_id,
                        "required_predecessor_step_id": predecessor_step_id,
                    },
                )
            predecessor_entry = step_entries.get(predecessor_step_id)
            response_data_path = predecessor_entry.response_data_path if predecessor_entry is not None else "data"
            for binding in required_spec.param_bindings:
                value = step.params.get(binding.target_param)
                if not isinstance(value, str) or not is_dag_binding(value):
                    raise DagPlanValidationError(
                        "planner_binding_semantic_invalid",
                        (
                            f"步骤 {step.step_id} 的 required predecessor 绑定缺失或非绑定表达式: "
                            f"{binding.target_param}"
                        ),
                        metadata={
                            "target_api_id": entry.id,
                            "target_step_id": step.step_id,
                            "required_predecessor_api_id": required_spec.predecessor_api_id,
                            "required_predecessor_step_id": predecessor_step_id,
                            "target_param": binding.target_param,
                        },
                    )
                source_path = _normalize_predecessor_source_path(
                    binding.source_path,
                    response_data_path=response_data_path,
                )
                if not source_path:
                    continue
                expected_expression = _build_predecessor_binding_expression(
                    step_id=predecessor_step_id,
                    source_path=source_path,
                    select_mode=binding.select_mode,
                )
                if value != expected_expression:
                    raise DagPlanValidationError(
                        "planner_binding_semantic_invalid",
                        (
                            f"步骤 {step.step_id} 的 required predecessor 绑定不匹配: "
                            f"{binding.target_param}={value}"
                        ),
                        metadata={
                            "target_api_id": entry.id,
                            "target_step_id": step.step_id,
                            "required_predecessor_api_id": required_spec.predecessor_api_id,
                            "required_predecessor_step_id": predecessor_step_id,
                            "target_param": binding.target_param,
                            "expected_expression": expected_expression,
                            "actual_expression": value,
                        },
                    )
