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
from app.services.api_catalog.dag_bindings import DagBindingSyntaxError, collect_binding_step_ids
from app.services.api_catalog.schema import ApiCatalogEntry, ApiCatalogSearchResult

logger = logging.getLogger(__name__)
_QUERY_SAFE_METHODS = {"GET", "POST"}


class DagPlanValidationError(ValueError):
    """第三阶段 DAG 校验失败。"""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


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

    def __init__(self, llm_service: Any | None = None) -> None:
        """初始化第三阶段 DAG Planner。

        Args:
            llm_service: 可选的 LLM 调用服务。

        功能：
            第三阶段最看重的是图纸稳定性，因此允许由外层把 `/api_query` 专用模型显式
            注入进来，避免 Planner 在不同运行环境里命中不同默认后端。
        """
        self._llm = llm_service

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

        prompt = _build_planner_prompt(query, candidates, user_context, route_hint)
        raw_payload = await self._call_llm_json(prompt, trace_id=trace_id)
        if not raw_payload:
            logger.warning(
                "stage3 planner degraded trace_id=%s code=%s query=%s",
                trace_id or "-",
                "planner_parse_failed",
                _summarize_log_text(query),
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
    ) -> dict[str, ApiCatalogEntry]:
        """对查询 DAG 做结构与白名单校验。

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
        """
        allowed_entries_by_id = _build_allowed_entries_by_id(candidates)
        allowed_entries_by_path = _build_allowed_entries_by_path(candidates)
        plan_steps_by_id = {step.step_id: step for step in plan.steps}
        step_entries: dict[str, ApiCatalogEntry] = {}

        if len(plan_steps_by_id) != len(plan.steps):
            raise DagPlanValidationError("planner_duplicate_step_id", "Planner 生成了重复的 step_id。")

        dependency_graph: dict[str, set[str]] = {}
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

            step_entries[step.step_id] = entry
            dependency_graph[step.step_id] = set(step.depends_on)

        try:
            tuple(TopologicalSorter(dependency_graph).static_order())
        except CycleError as exc:
            raise DagPlanValidationError("planner_cycle_detected", "Planner 生成的 DAG 存在循环依赖。") from exc

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

            parsed = _parse_json_payload(raw)
            if parsed:
                return parsed

            logger.warning(
                "Planner LLM returned non-json payload trace_id=%s on attempt %s/%s raw=%s",
                trace_id or "-",
                attempt + 1,
                max_attempts,
                _summarize_log_text(raw),
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
    for candidate in candidates:
        # 这里故意保留“第一次命中的条目”，因为候选集已经按召回顺序排好，
        # 后续校验阶段只需要知道某条路径是否合法，不需要再次重排。
        allowed_entries.setdefault(candidate.entry.path, candidate.entry)
    return allowed_entries


def _build_allowed_entries_by_id(candidates: list[ApiCatalogSearchResult]) -> dict[str, ApiCatalogEntry]:
    """按接口 ID 整理候选接口，避免同一路径不同方法时发生歧义。"""
    allowed_entries: dict[str, ApiCatalogEntry] = {}
    for candidate in candidates:
        allowed_entries.setdefault(candidate.entry.id, candidate.entry)
    return allowed_entries


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
    return f"""# Role
你是一个企业级 API 工作流编排引擎 (Planner)。
你的任务是：根据用户的自然语言请求，以及系统提供的[可用 API 列表]，编排出一个高效的 API 调用执行计划 (DAG)。

用户请求：{query}
用户上下文：{context_str}
第二阶段路由提示：{json.dumps(route_hint_payload, ensure_ascii=False)}

# Execution Rules (安全红线)
1. 绝对禁止使用 `operation_safety != query` 的接口。
2. 你只能使用以下 `operation_safety=query` 且 `method in [GET, POST]` 的接口来拉取数据。
3. 你不能编造 API 路径、参数名或步骤 ID。

# Available APIs
{candidate_block}

# Execution Rules (核心规则)
1. 最小化调用：只调用对回答用户问题有帮助的 API。
2. 并发优先：如果多个 API 没有数据依赖，`depends_on` 必须为空数组。
3. 上下文传递：如果步骤 B 需要步骤 A 的返回结果作为入参，必须使用 JSONPath 绑定。
4. JSONPath 语法只允许使用：
   - `$[step_id.data].field`
   - `$[step_id.data][*].field`
5. 如果某个参数是从上游步骤提取出来的，该上游步骤必须出现在 `depends_on` 中。
6. 所有步骤的 `step_id` 必须唯一，且只使用字母、数字、下划线。

# Output Format
必须返回合法 JSON，结构如下：
{{
  "plan_id": "dag_xxx",
  "steps": [
    {{
      "step_id": "step_1",
      "api_id": "endpoint_xxx",
      "api_path": "/api/xxx",
      "params": {{}},
      "depends_on": []
    }}
  ]
}}

# Example
如果先查客户，再根据客户 ID 查订单：
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
      "params": {{"customer_ids": "$[step_customers.data][*].id"}},
      "depends_on": ["step_customers"]
    }}
  ]
}}
"""


def _parse_json_payload(raw: str) -> dict[str, Any]:
    """从 Planner 输出中尽量提取首个 JSON 对象。

    设计说明：
        这里刻意复制第二阶段的“脏 JSON 清洗”策略，而不是直接复用内部私有函数。
        原因是第三阶段一旦出问题，定位链路需要尽量本地自洽，避免让 Planner 的
        可用性绑定到第二阶段私有实现细节上。
    """
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and start < end:
        text = text[start : end + 1]

    text = _strip_json_comments(text)
    text = _strip_trailing_commas(text)

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        logger.debug("Failed to parse planner JSON: %s", raw[:300])
        return {}

    return payload if isinstance(payload, dict) else {}


def _summarize_log_text(text: str | None, *, limit: int = 240) -> str:
    """压缩日志文本，保留排查 DAG 脏输出所需的首段上下文。"""
    normalized = " ".join((text or "").split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[:limit]}..."


def _strip_json_comments(text: str) -> str:
    """删除 JSON 中的注释，同时保留字符串字面量。"""
    result: list[str] = []
    index = 0
    in_string = False
    escaped = False

    while index < len(text):
        char = text[index]
        next_char = text[index + 1] if index + 1 < len(text) else ""

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
            while index < len(text) and text[index] not in ("\n", "\r"):
                index += 1
            continue

        if char == "/" and next_char == "*":
            index += 2
            while index + 1 < len(text) and not (text[index] == "*" and text[index + 1] == "/"):
                index += 1
            index += 2
            continue

        result.append(char)
        index += 1

    return "".join(result)


def _strip_trailing_commas(text: str) -> str:
    """删除对象或数组闭合前的尾逗号。"""
    result: list[str] = []
    index = 0
    in_string = False
    escaped = False

    while index < len(text):
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
            while lookahead < len(text) and text[lookahead].isspace():
                lookahead += 1
            if lookahead < len(text) and text[lookahead] in ("]", "}"):
                index += 1
                continue

        result.append(char)
        index += 1

    return "".join(result)
