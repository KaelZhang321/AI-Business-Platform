"""Stage 3 图事实校验器。

功能：
    在白名单、环检测和 JSONPath 语法校验之后，继续回答第三阶段最关键的问题：

    1. Planner 声称的字段传递路径，图里是否真实存在
    2. 这条路径是不是标识字段的正确解析链
    3. 上下游字段基数是否对齐，是否需要进入 `WAIT_SELECT`

设计动机：
    仅靠候选白名单无法防住“把 Role.name 当成 Role.id 传给删除/详情接口”这类高危误编排。
    这里把图事实固化为同步校验逻辑，让 Stage 3 成为真正的硬闸，而不是经验判断。
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models.schemas.api_query import ApiQueryExecutionPlan
from app.services.api_catalog.dag_bindings import is_dag_binding, parse_binding_expression
from app.services.api_catalog.graph_models import ApiCatalogSubgraphResult
from app.services.api_catalog.schema import ApiCatalogEntry

_REQUEST_LOCATIONS = {"queryParams", "body", "path", "header"}


class GraphPlanValidationError(ValueError):
    """图事实校验失败。

    功能：
        用结构化错误码表达 Stage 3 的确定性校验结果，方便 workflow 在后续波次把
        `planner_cardinality_mismatch` 精准翻译成 `WAIT_SELECT`，而不是统一折叠成普通失败。

    入参业务含义：
        - `code`：稳定错误码，供 workflow / 动态 UI / 审计链路复用
        - `message`：可直接进入日志与调试信息的说明文案
        - `metadata`：可恢复暂停态需要的附加事实，例如 `pause_type`
    """

    def __init__(self, code: str, message: str, metadata: dict[str, object] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.metadata = metadata or {}


@dataclass(frozen=True, slots=True)
class _BoundParameter:
    """步骤参数里的单条绑定事实。"""

    source_step_id: str
    target_step_id: str
    target_param_path: str
    target_inject_path: str
    expression: str


class GraphPlanValidator:
    """基于 Stage 2 子图做 Stage 3 硬校验。

    功能：
        该校验器只消费 Stage 2 已经抽出的 `ApiCatalogSubgraphResult`，不直接访问图库。
        这样可以把“在线怎么拿子图”与“图事实怎么校验”两件事解耦，避免 Stage 3 再次耦合 Neo4j。

    返回值约束：
        - 校验通过时不返回业务值，只代表当前 plan 可以进入执行阶段
        - 校验失败时统一抛 `GraphPlanValidationError`

    Edge Cases:
        - 单步直达或无跨步骤绑定的 plan 允许没有子图
        - 图降级时，只要 plan 依赖跨步骤数据传递，就必须保守拦截
        - `array -> scalar` 不再混入普通字段错误，而是抛 `planner_cardinality_mismatch`
    """

    def validate_plan(
        self,
        *,
        plan: ApiQueryExecutionPlan,
        step_entries: dict[str, ApiCatalogEntry],
        subgraph_result: ApiCatalogSubgraphResult | None,
    ) -> None:
        """校验 Planner 生成的字段传递链。

        Args:
            plan: 已通过基础结构校验的执行计划。
            step_entries: `step_id -> ApiCatalogEntry` 的白名单映射。
            subgraph_result: Stage 2 返回的局部子图摘要。

        Raises:
            GraphPlanValidationError: 当字段路径、标识解析链或基数对齐不成立时抛出。

        Edge Cases:
            - `subgraph_result is None` 代表当前请求没有拿到图事实，不等价于“图中没有依赖”
            - 只有真正存在跨步骤数据绑定时，才把图降级视为阻断条件
        """

        bound_parameters = list(_collect_bound_parameters(plan, step_entries))
        if _plan_requires_graph_validation(plan) and _is_graph_unavailable(subgraph_result):
            raise GraphPlanValidationError(
                "planner_graph_degraded_forbidden",
                "当前计划依赖图事实校验，但 Stage 2 未能提供可用子图，已保守终止执行。",
                metadata={
                    "degraded_reason": subgraph_result.degraded_reason if subgraph_result else "subgraph_missing"
                },
            )

        if subgraph_result is None:
            return

        self._validate_required_identifier_resolution(
            plan=plan,
            step_entries=step_entries,
            subgraph_result=subgraph_result,
        )
        for bound_parameter in bound_parameters:
            self._validate_bound_parameter(
                bound_parameter=bound_parameter,
                step_entries=step_entries,
                subgraph_result=subgraph_result,
            )

    def _validate_required_identifier_resolution(
        self,
        *,
        plan: ApiQueryExecutionPlan,
        step_entries: dict[str, ApiCatalogEntry],
        subgraph_result: ApiCatalogSubgraphResult,
    ) -> None:
        """校验目标 step 是否显式解决了必需的标识字段。

        功能：
            这一步拦截的是“图里明明知道详情/删除需要 Role.id，但 plan 里根本没把它接起来”
            这种漏编排场景。若放到执行阶段才发现，前端和业务系统只能看到一条模糊的缺参错误。
        """

        provided_param_paths_by_step = {
            step.step_id: set(_collect_provided_param_paths(step.params)) for step in plan.steps
        }

        for step in plan.steps:
            entry = step_entries[step.step_id]
            for required_param in entry.param_schema.required:
                candidate_target_paths = _resolve_target_inject_paths(entry, required_param)
                has_identifier_path = any(
                    field_path.consumer_api_id == entry.id
                    and field_path.is_identifier
                    and field_path.target_inject_path in candidate_target_paths
                    for field_path in subgraph_result.field_paths
                )
                if not has_identifier_path:
                    continue

                if required_param in provided_param_paths_by_step[step.step_id]:
                    continue

                raise GraphPlanValidationError(
                    "planner_missing_identifier_resolution",
                    f"步骤 {step.step_id} 缺少必需的标识字段解析链: {required_param}",
                    metadata={
                        "step_id": step.step_id,
                        "api_id": entry.id,
                        "required_param": required_param,
                        "target_inject_paths": candidate_target_paths,
                    },
                )

    def _validate_bound_parameter(
        self,
        *,
        bound_parameter: _BoundParameter,
        step_entries: dict[str, ApiCatalogEntry],
        subgraph_result: ApiCatalogSubgraphResult,
    ) -> None:
        """校验单条跨步骤字段传递。

        功能：
            把“producer -> field -> consumer”的事实，映射回 planner 的
            `JSONPath binding -> target param`，这是 Stage 3 图安全闸的核心判断。
        """

        producer_entry = step_entries[bound_parameter.source_step_id]
        consumer_entry = step_entries[bound_parameter.target_step_id]
        binding_source_path = _normalize_binding_source_path(bound_parameter.expression)
        pair_paths = [
            field_path
            for field_path in subgraph_result.field_paths
            if field_path.producer_api_id == producer_entry.id and field_path.consumer_api_id == consumer_entry.id
        ]
        if not pair_paths:
            raise GraphPlanValidationError(
                "planner_missing_field_path",
                f"步骤 {bound_parameter.target_step_id} 缺少从 {bound_parameter.source_step_id} 到当前参数的图路径。",
                metadata={
                    "source_step_id": bound_parameter.source_step_id,
                    "target_step_id": bound_parameter.target_step_id,
                    "target_inject_path": bound_parameter.target_inject_path,
                },
            )

        target_paths = [
            field_path
            for field_path in pair_paths
            if field_path.target_inject_path == bound_parameter.target_inject_path
        ]
        if not target_paths:
            raise GraphPlanValidationError(
                "planner_missing_field_path",
                f"步骤 {bound_parameter.target_step_id} 的参数 {bound_parameter.target_param_path} 未命中任何合法注入路径。",
                metadata={
                    "source_step_id": bound_parameter.source_step_id,
                    "target_step_id": bound_parameter.target_step_id,
                    "target_inject_path": bound_parameter.target_inject_path,
                },
            )

        exact_paths = [
            field_path
            for field_path in target_paths
            if _normalize_graph_source_path(
                field_path.source_extract_path,
                response_data_path=producer_entry.response_data_path,
            )
            == binding_source_path
        ]
        if not exact_paths:
            raise GraphPlanValidationError(
                "planner_invalid_field_transfer",
                (
                    f"步骤 {bound_parameter.target_step_id} 把 {bound_parameter.expression} 绑定到了 "
                    f"{bound_parameter.target_param_path}，但图中不存在这条字段传递事实。"
                ),
                metadata={
                    "source_step_id": bound_parameter.source_step_id,
                    "target_step_id": bound_parameter.target_step_id,
                    "target_inject_path": bound_parameter.target_inject_path,
                    "binding_source_path": binding_source_path,
                },
            )

        exact_valid_paths = [
            field_path for field_path in exact_paths if field_path.source_array_mode == field_path.target_array_mode
        ]
        if exact_valid_paths:
            return

        mismatch_path = exact_paths[0]
        metadata = {
            "source_step_id": bound_parameter.source_step_id,
            "target_step_id": bound_parameter.target_step_id,
            "producer_api_id": producer_entry.id,
            "consumer_api_id": consumer_entry.id,
            "semantic_key": mismatch_path.semantic_key,
            "source_array_mode": mismatch_path.source_array_mode,
            "target_array_mode": mismatch_path.target_array_mode,
        }
        if mismatch_path.source_array_mode and not mismatch_path.target_array_mode:
            # 数组结果不能在没有人工选择的情况下直接坍缩为单值，否则很容易误删、误详情定位。
            metadata.update(
                {
                    "pause_type": "WAIT_SELECT",
                    "pause_reason": "cardinality_mismatch",
                    "selection_mode": "single",
                }
            )
        raise GraphPlanValidationError(
            "planner_cardinality_mismatch",
            f"步骤 {bound_parameter.target_step_id} 的字段基数与图事实不一致，已阻断执行。",
            metadata=metadata,
        )


def _plan_requires_graph_validation(plan: ApiQueryExecutionPlan) -> bool:
    """判断当前 plan 是否已经进入图事实必需区间。"""

    return any(step.depends_on or _payload_contains_binding(step.params) for step in plan.steps)


def _is_graph_unavailable(subgraph_result: ApiCatalogSubgraphResult | None) -> bool:
    """统一判断当前请求是否缺少可用图事实。"""

    return subgraph_result is None or subgraph_result.graph_degraded


def _collect_bound_parameters(
    plan: ApiQueryExecutionPlan,
    step_entries: dict[str, ApiCatalogEntry],
) -> list[_BoundParameter]:
    """从 plan 中抽取所有跨步骤绑定。

    功能：
        这里显式把绑定表达式和目标参数路径对应起来，避免后续校验阶段再去重新遍历整棵
        params 树，降低字段路径判断逻辑的复杂度。
    """

    bound_parameters: list[_BoundParameter] = []
    for step in plan.steps:
        entry = step_entries[step.step_id]
        for target_param_path, expression in _iter_binding_expressions(step.params):
            for target_inject_path in _resolve_target_inject_paths(entry, target_param_path):
                bound_parameters.append(
                    _BoundParameter(
                        source_step_id=parse_binding_expression(expression).step_id,
                        target_step_id=step.step_id,
                        target_param_path=target_param_path,
                        target_inject_path=target_inject_path,
                        expression=expression,
                    )
                )
    return bound_parameters


def _payload_contains_binding(payload: object) -> bool:
    """判断当前参数树中是否存在 DAG 绑定表达式。"""

    if isinstance(payload, dict):
        return any(_payload_contains_binding(value) for value in payload.values())
    if isinstance(payload, list):
        return any(_payload_contains_binding(item) for item in payload)
    return is_dag_binding(payload)


def _iter_binding_expressions(payload: object, *, prefix: str = "") -> list[tuple[str, str]]:
    """递归提取 `params` 中的绑定表达式。"""

    results: list[tuple[str, str]] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            child_prefix = f"{prefix}.{key}" if prefix else key
            results.extend(_iter_binding_expressions(value, prefix=child_prefix))
        return results
    if isinstance(payload, list):
        for index, item in enumerate(payload):
            child_prefix = f"{prefix}[{index}]"
            results.extend(_iter_binding_expressions(item, prefix=child_prefix))
        return results
    if is_dag_binding(payload):
        results.append((prefix, str(payload)))
    return results


def _collect_provided_param_paths(payload: object, *, prefix: str = "") -> list[str]:
    """递归收集当前 step 显式提供了哪些参数路径。"""

    paths: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            child_prefix = f"{prefix}.{key}" if prefix else key
            paths.extend(_collect_provided_param_paths(value, prefix=child_prefix))
        return paths
    if isinstance(payload, list):
        for index, item in enumerate(payload):
            child_prefix = f"{prefix}[{index}]"
            paths.extend(_collect_provided_param_paths(item, prefix=child_prefix))
        return paths
    if prefix:
        paths.append(prefix)
    return paths


def _resolve_target_inject_paths(entry: ApiCatalogEntry, param_path: str) -> list[str]:
    """把 step 参数路径映射为图中的注入路径。

    功能：
        图同步记录的是 `body.roleId / queryParams.pageNum` 这类物理路径；而 planner params
        只知道逻辑字段名。这里优先复用请求字段画像，缺失时再按方法做最小保守推断。
    """

    profile_paths = sorted(
        {
            profile.json_path
            for profile in entry.request_field_profiles
            if _strip_request_location(profile.json_path) == param_path
        }
    )
    if profile_paths:
        return profile_paths

    default_location = "queryParams" if entry.method == "GET" else "body"
    return [f"{default_location}.{param_path}"]


def _strip_request_location(path: str) -> str:
    """去掉图请求路径前缀，便于与 planner params 路径对齐。"""

    first_segment, _, remainder = path.partition(".")
    if first_segment in _REQUEST_LOCATIONS and remainder:
        return remainder
    return path


def _normalize_binding_source_path(expression: str) -> str:
    """把 binding 表达式折叠成相对 `step.data` 根节点的路径。"""

    parsed = parse_binding_expression(expression)
    return "".join(parsed.tokens)


def _normalize_graph_source_path(source_extract_path: str, *, response_data_path: str) -> str:
    """把图里记录的响应路径折叠成 binding 可比较的相对路径。

    功能：
        Stage 4 执行时真正暴露给下游 binding 的是 `execution_result.data`，而不是业务系统原始响应。
        因此校验时必须先把图中的 `source_extract_path` 剥离到 `response_data_path` 之下，再与
        `$[step_x.data]...` 做比较。
    """

    normalized_path = source_extract_path.strip()
    normalized_root = response_data_path.strip()
    if normalized_root and normalized_path == normalized_root:
        return ""
    if normalized_root and normalized_path.startswith(f"{normalized_root}."):
        normalized_path = normalized_path[len(normalized_root) :]
    elif normalized_root and normalized_path.startswith(f"{normalized_root}[]"):
        normalized_path = normalized_path[len(normalized_root) :]
    return normalized_path.replace("[]", "[*]")
