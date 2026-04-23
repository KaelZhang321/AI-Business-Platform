"""
API Catalog — 第二阶段路由与参数提取器

职责拆分：
1. 轻量路由：在真正检索前先提取 `query_domains + business_intents`
2. 候选内路由：在分层召回结果中选出最合适的接口
3. 参数提取：只保留 Schema 允许的字段，拦截幻觉参数

设计动机：
- Router-first 是为了把“先分诊再召回”的链路落到代码里，避免全域 Top-K 抢占
- 结构化输出 + 一次重试是为了把路由失败控制在第二阶段，不把脏 JSON 继续传下去
- 所有 LLM 输出都视为不可信，必须经过 allowlist 与 Schema 双重清洗
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.core.config import settings
from app.models.schemas import ApiQueryRoutingResult
from app.services.api_catalog.business_intents import (
    NOOP_BUSINESS_INTENT,
    normalize_business_intent_code,
)
from app.services.api_catalog.schema import ApiCatalogEntry, ApiCatalogSearchResult
from app.utils.json_utils import parse_dirty_json_object, summarize_log_text

logger = logging.getLogger(__name__)

_NOOP_BUSINESS_INTENT = NOOP_BUSINESS_INTENT
_UNKNOWN_DOMAIN = "unknown"


class ApiParamExtractor:
    """通过 LLM 完成第二阶段轻量路由、候选接口选择与参数提取。

    功能：
        统一承接 Stage-2 的两类模型能力，避免 route 层分别维护多个“半可信”解析器。

    Edge Cases:
        - 轻量路由 JSON 解析失败时，不再猜测 domain，而是显式返回 fallback 状态
        - 候选内路由若返回未知 `selected_api_id`，仅允许回退到当前候选集中的 Top-1
        - 参数提取始终以 Schema 为准，防止宽查询或越权字段透传
    """

    def __init__(self, llm_service: Any | None = None) -> None:
        """初始化第二阶段参数提取器。

        Args:
            llm_service: 可选的 LLM 调用服务。

        功能：
            `api_query` 现在要求全链路固定走 Ark，但其他测试和旧调用点仍可能依赖默认
            `LLMService`。这里保留可注入能力，避免把模型供应商选择硬编码进业务逻辑。
        """
        self._llm = llm_service

    def _get_llm(self):
        """懒加载 LLM 服务，避免无调用时初始化模型客户端。"""
        if self._llm is None:
            from app.services.llm_service import LLMService

            self._llm = LLMService()
        return self._llm

    async def route_query(
        self,
        query: str,
        user_context: dict[str, Any] | None = None,
        *,
        allowed_business_intents: set[str] | None = None,
        trace_id: str | None = None,
    ) -> ApiQueryRoutingResult:
        """在召回前执行轻量意图路由。

        Args:
            query: 用户自然语言原始请求。
            user_context: 已从 JWT 或请求态提取出的用户上下文。
            allowed_business_intents: 当前网关允许识别的业务意图白名单。

        Returns:
            仅填充 `query_domains` / `business_intents` / `reasoning` 的路由结果。

        Edge Cases:
            - 若模型未返回可解析 JSON，则返回 `route_status=fallback`
            - 若模型只给出 `unknown` 域，同样返回 fallback，避免后续误查全域
        """
        prompt = _build_route_only_prompt(query, user_context, allowed_business_intents)
        result = await self._call_llm_json(prompt, scenario="route_query", trace_id=trace_id)
        if not result:
            logger.warning(
                "stage2 routing degraded trace_id=%s code=%s query=%s",
                trace_id or "-",
                "routing_parse_failed",
                summarize_log_text(query),
            )
            return ApiQueryRoutingResult(
                business_intents=[_NOOP_BUSINESS_INTENT],
                route_status="fallback",
                route_error_code="routing_parse_failed",
                reasoning="轻量路由未返回可解析 JSON。",
            )

        query_domains = _sanitize_route_domains(result.get("query_domains"))
        business_intents = _sanitize_business_intents(
            result.get("business_intents"),
            allowed=allowed_business_intents,
            fallback=[_NOOP_BUSINESS_INTENT],
        )
        reasoning = _safe_string(result.get("reasoning"))
        is_multi_domain = bool(result.get("is_multi_domain")) or len(query_domains) > 1

        if not query_domains:
            logger.info(
                "stage2 routing degraded trace_id=%s code=%s intents=%s reasoning=%s",
                trace_id or "-",
                "routing_unknown_domain",
                business_intents,
                reasoning or "",
            )
            return ApiQueryRoutingResult(
                business_intents=business_intents,
                is_multi_domain=False,
                reasoning=reasoning or "未识别到可用业务域。",
                route_status="fallback",
                route_error_code="routing_unknown_domain",
            )

        return ApiQueryRoutingResult(
            query_domains=query_domains,
            business_intents=business_intents,
            is_multi_domain=is_multi_domain,
            reasoning=reasoning,
            route_status="ok",
        )

    async def extract(
        self,
        query: str,
        candidates: list[ApiCatalogSearchResult],
        user_context: dict[str, Any] | None = None,
    ) -> tuple[ApiCatalogEntry | None, dict[str, Any]]:
        """兼容旧调用方式，返回最终选中的接口与参数。"""
        routing_result = await self.extract_routing_result(query, candidates, user_context)
        selected_id = routing_result.selected_api_id
        entry = next((candidate.entry for candidate in candidates if candidate.entry.id == selected_id), None)
        return entry, dict(routing_result.params)

    async def extract_routing_result(
        self,
        query: str,
        candidates: list[ApiCatalogSearchResult],
        user_context: dict[str, Any] | None = None,
        *,
        allowed_business_intents: set[str] | None = None,
        routing_hints: ApiQueryRoutingResult | None = None,
        trace_id: str | None = None,
    ) -> ApiQueryRoutingResult:
        """在候选集内完成接口选择与参数提取。

        Args:
            query: 用户自然语言原始请求。
            candidates: 分层召回后的候选接口列表。
            user_context: 用户上下文。
            allowed_business_intents: 允许透传的业务意图白名单。
            routing_hints: 轻量路由阶段的先验结果，用于约束候选内选择。

        Returns:
            包含 `selected_api_id`、`params`、`query_domains`、`business_intents` 的完整结果。

        Edge Cases:
            - 候选集为空时直接返回空结果，由 route 层决定是否降级
            - 候选内 LLM 再次解析失败时，不再默认命中 Top-1，避免误查
        """
        if not candidates:
            return ApiQueryRoutingResult(
                query_domains=list(routing_hints.query_domains) if routing_hints else [],
                business_intents=list(routing_hints.business_intents) if routing_hints else [_NOOP_BUSINESS_INTENT],
                route_status="fallback",
                route_error_code="candidate_set_empty",
            )

        business_intent_fallback = (
            list(routing_hints.business_intents)
            if routing_hints and routing_hints.business_intents
            else [_NOOP_BUSINESS_INTENT]
        )

        if len(candidates) == 1:
            entry = candidates[0].entry
            # 单候选时不再做“接口选择”，但参数仍必须经过 LLM + Schema 双重治理。
            params = await self._extract_params(query, entry, user_context, trace_id=trace_id)
            return ApiQueryRoutingResult(
                selected_api_id=entry.id,
                query_domains=_sanitize_query_domains(
                    routing_hints.query_domains if routing_hints else None,
                    candidates,
                    entry.domain,
                ),
                business_intents=_sanitize_business_intents(
                    business_intent_fallback,
                    allowed=allowed_business_intents,
                    fallback=[_NOOP_BUSINESS_INTENT],
                ),
                is_multi_domain=bool(routing_hints.is_multi_domain) if routing_hints else False,
                reasoning=routing_hints.reasoning if routing_hints else None,
                params=params,
            )

        return await self._route_and_extract(
            query,
            candidates,
            user_context,
            allowed_business_intents=allowed_business_intents,
            routing_hints=routing_hints,
            trace_id=trace_id,
        )

    async def _extract_params(
        self,
        query: str,
        entry: ApiCatalogEntry,
        user_context: dict[str, Any] | None,
        *,
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        """单接口参数提取。

        这里复用同一套 JSON 调用治理，目的是让单候选路径也具备相同的抗脏输出能力。
        """
        prompt = _build_extract_only_prompt(query, entry, user_context)
        params = await self._invoke_llm_json(prompt, scenario="extract_params", trace_id=trace_id)
        return _validate_params(params, entry)

    async def _route_and_extract(
        self,
        query: str,
        candidates: list[ApiCatalogSearchResult],
        user_context: dict[str, Any] | None,
        *,
        allowed_business_intents: set[str] | None,
        routing_hints: ApiQueryRoutingResult | None,
        trace_id: str | None,
    ) -> ApiQueryRoutingResult:
        """多候选场景下的接口路由与参数提取。

        功能：
            把“选哪个接口”和“提什么参数”绑定在一次结构化输出里，减少多次模型调用引入的漂移。
        """
        prompt = _build_route_and_extract_prompt(query, candidates, user_context, routing_hints)
        result = await self._invoke_llm_json(prompt, scenario="route_and_extract", trace_id=trace_id)
        if not result:
            logger.warning(
                "stage2 route_and_extract degraded trace_id=%s code=%s domains=%s",
                trace_id or "-",
                "route_and_extract_parse_failed",
                list(routing_hints.query_domains) if routing_hints else [],
            )
            return ApiQueryRoutingResult(
                query_domains=list(routing_hints.query_domains) if routing_hints else [],
                business_intents=list(routing_hints.business_intents) if routing_hints else [_NOOP_BUSINESS_INTENT],
                is_multi_domain=bool(routing_hints.is_multi_domain) if routing_hints else False,
                reasoning=routing_hints.reasoning if routing_hints else "候选内路由未返回可解析 JSON。",
                route_status="fallback",
                route_error_code="route_and_extract_parse_failed",
            )

        selected_id = result.get("selected_api_id")
        raw_params = result.get("params", {})
        entry = next((candidate.entry for candidate in candidates if candidate.entry.id == selected_id), None)
        if entry is None:
            # LLM 只能在候选集里选接口；一旦越界，只允许回退到当前最相关候选，避免误调不存在的 API。
            logger.warning(
                "stage2 extractor selected unknown api trace_id=%s selected_api_id=%s fallback_api_id=%s",
                trace_id or "-",
                selected_id,
                candidates[0].entry.id,
            )
            entry = candidates[0].entry

        query_domain_fallback = (
            routing_hints.query_domains[0] if routing_hints and routing_hints.query_domains else entry.domain
        )
        business_intent_fallback = (
            list(routing_hints.business_intents)
            if routing_hints and routing_hints.business_intents
            else [_NOOP_BUSINESS_INTENT]
        )

        return ApiQueryRoutingResult(
            selected_api_id=entry.id,
            query_domains=_sanitize_query_domains(result.get("query_domains"), candidates, query_domain_fallback),
            business_intents=_sanitize_business_intents(
                result.get("business_intents"),
                allowed=allowed_business_intents,
                fallback=business_intent_fallback,
            ),
            is_multi_domain=bool(result.get("is_multi_domain"))
            or (bool(routing_hints.is_multi_domain) if routing_hints else False),
            reasoning=_safe_string(result.get("reasoning")) or (routing_hints.reasoning if routing_hints else None),
            params=_validate_params(raw_params, entry),
        )

    async def _call_llm_json(
        self,
        prompt: str,
        *,
        scenario: str,
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        """以“结构化优先、文本兜底”的方式调用 LLM。

        功能：
            首次尝试使用 JSON Mode，失败后退回普通文本模式重试一次。
            这样既能利用支持 `response_format` 的后端，又不会把兼容层限制硬编码死。

        Args:
            prompt: 当前场景的提示词。
            scenario: 日志使用的场景标签，便于区分 route / extract / render 问题。

        Returns:
            解析后的 JSON 对象；失败时返回空字典。
        """
        llm = self._get_llm()
        max_attempts = max(1, settings.api_query_route_retry_count + 1)

        for attempt in range(max_attempts):
            use_structured_output = attempt == 0
            try:
                raw = await llm.chat(
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.0,
                    response_format={"type": "json_object"} if use_structured_output else None,
                    timeout_seconds=settings.api_query_route_timeout_seconds,
                )
            except Exception as exc:
                logger.warning(
                    "LLM %s failed trace_id=%s on attempt %s/%s: %s",
                    scenario,
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
                "LLM %s returned non-json payload trace_id=%s on attempt %s/%s raw=%s",
                scenario,
                trace_id or "-",
                attempt + 1,
                max_attempts,
                summarize_log_text(raw),
            )

        return {}

    async def _invoke_llm_json(
        self,
        prompt: str,
        *,
        scenario: str,
        trace_id: str | None,
    ) -> dict[str, Any]:
        """兼容旧测试替身签名的 LLM JSON 调用包装器。

        功能：
            第二阶段已经需要把 `trace_id` 打进日志，但现有测试和少量替身仍只接受
            `scenario` 参数。这里做一次兼容包装，确保主逻辑先平滑升级，不因测试桩签名
            漂移阻断迭代。
        """
        try:
            return await self._call_llm_json(prompt, scenario=scenario, trace_id=trace_id)
        except TypeError:
            return await self._call_llm_json(prompt, scenario=scenario)


def _build_extract_only_prompt(
    query: str,
    entry: ApiCatalogEntry,
    user_context: dict[str, Any] | None,
) -> str:
    """构建单接口参数提取提示词。"""
    schema_str = json.dumps(entry.param_schema.model_dump(), ensure_ascii=False, indent=2)
    ctx_str = json.dumps(user_context or {}, ensure_ascii=False)
    return f"""你是一个参数提取助手。根据用户输入从接口参数 Schema 中提取对应参数值。

用户输入：{query}
接口描述：{entry.description}
用户上下文（可直接填入参数）：{ctx_str}

参数 Schema：
{schema_str}

规则：
1. 只输出 Schema 中定义的参数，不要添加额外键
2. 用户未提及的可选参数不要包含
3. 类型严格匹配 Schema 中的 type
4. 直接输出 JSON 对象，不要解释或包含 markdown 代码块

输出："""


def _build_route_only_prompt(
    query: str,
    user_context: dict[str, Any] | None,
    allowed_business_intents: set[str] | None,
) -> str:
    """构建召回前的轻量路由提示词。"""
    # 1.`CRM`
    # - 核心职责：管理外部客户、联系人、潜在商机、销售线索等。
    # - 映射词汇：客户、联系人、客户画像、商机、线索、买家、公海、档案。
    ctx_str = json.dumps(user_context or {}, ensure_ascii=False)
    allowed_intents = sorted(allowed_business_intents or {_NOOP_BUSINESS_INTENT})
    intents_str = json.dumps(allowed_intents, ensure_ascii=False)
    return f"""# Role
你是一个企业级 API 网关的“高级智能路由与意图解析引擎”。你的核心任务是：深度分析用户的自然语言输入，将其精准拆解为“底层数据查询域（Read）”和“业务变更意图（Write）”两部分。

用户输入：{query}
用户上下文：{ctx_str}

# Domain Mapping Rules
1. `OMS`
   - 核心职责：管理外部客户、联系人、订单、交付、规划、疗效等。
   - 映射词汇：客户、联系人、客户画像、订单、交付、规划、疗效。
2. `IAM`
   - 核心职责：管理企业内部组织架构、员工账号、角色、权限、部门等。
   - 映射词汇：权限、账号、角色、员工、部门、组织架构、销售部。
3. 其他兼容域
   - 若用户明确涉及 `ERP`、`MEETING_BI` 等现有业务域，可直接输出对应域编码。
   - 若完全不属于已知业务域，则输出 `["unknown"]`。

# Action Mapping Rules
- `saveToServer`: 用户意图更新、保存、修改、写入目标或信息。
- `deleteCustomer`: 用户意图废弃、删除、下线某位客户或数据。
- `none`: 纯查询请求，没有任何变更或写入意图。
- 只允许使用这些业务意图编码：{intents_str}

# Output Constraint
必须且只能输出合法的纯 JSON 字符串，不要包含 Markdown、前缀说明或注释。
JSON 结构必须包含：
- `query_domains`
- `business_intents`
- `is_multi_domain`
- `reasoning`

规则：
- `query_domains` 只输出领域编码，不要输出接口名
- `business_intents` 只描述业务意图，不要输出 `remoteQuery` / `remoteMutation` 等前端动作
- 如果命中多个域，`is_multi_domain` 必须为 `true`

# Few-Shot Examples
User: 帮我查一下王总的联系方式。
Assistant: {{"query_domains":["OMS"],"business_intents":["none"],"is_multi_domain":false,"reasoning":"仅需要查询外部客户联系人，无任何数据修改意图。"}}

User: 查一下华东区销售部有哪些人，顺便看看他们名下各自有多少大客户。
Assistant: {{"query_domains":["IAM","OMS"],"business_intents":["none"],"is_multi_domain":true,"reasoning":"查询内部部门人员与其名下客户，属于跨域纯查询。"}}

User: 帮我调出客户C001的档案，然后把他的下月核心目标更新为每周3次有氧。
Assistant: {{"query_domains":["OMS"],"business_intents":["saveToServer"],"is_multi_domain":false,"reasoning":"需要先查询客户档案，再准备保存更新后的业务目标。"}}

User: 看看我名下有哪些无效的公海线索，直接把那个叫测试公司的记录删掉。
Assistant: {{"query_domains":["OMS"],"business_intents":["deleteCustomer"],"is_multi_domain":false,"reasoning":"查询线索属于CRM，且包含明确删除客户记录的意图。"}}

User: 帮我订一张明天上午飞北京的头等舱机票。
Assistant: {{"query_domains":["unknown"],"business_intents":["none"],"is_multi_domain":false,"reasoning":"当前请求不属于已知业务域。"}}

输出格式：
{{"query_domains":["oms"],"business_intents":["none"],"is_multi_domain":false,"reasoning":"..."}}"""


def _build_route_and_extract_prompt(
    query: str,
    candidates: list[ApiCatalogSearchResult],
    user_context: dict[str, Any] | None,
    routing_hints: ApiQueryRoutingResult | None,
) -> str:
    """构建候选内路由与参数提取提示词。"""
    ctx_str = json.dumps(user_context or {}, ensure_ascii=False)
    route_hint_payload = {
        "query_domains": list(routing_hints.query_domains) if routing_hints else [],
        "business_intents": list(routing_hints.business_intents) if routing_hints else [_NOOP_BUSINESS_INTENT],
        "is_multi_domain": bool(routing_hints.is_multi_domain) if routing_hints else False,
        "reasoning": routing_hints.reasoning if routing_hints else None,
    }
    candidates_str = "\n".join(
        (
            f"- id: {candidate.entry.id}\n"
            f"  domain: {candidate.entry.domain}\n"
            f"  描述: {candidate.entry.description}\n"
            f"  业务意图: {json.dumps(candidate.entry.business_intents, ensure_ascii=False)}\n"
            f"  参数Schema: {json.dumps(candidate.entry.param_schema.model_dump(), ensure_ascii=False)}"
        )
        for candidate in candidates
    )
    return f"""你是一个接口路由 + 参数提取助手。

用户输入：{query}
用户上下文：{ctx_str}
轻量路由提示：{json.dumps(route_hint_payload, ensure_ascii=False)}

候选接口列表：
{candidates_str}

任务：
1. 从候选接口中选择最匹配的接口（selected_api_id）
2. 输出最终命中的 query_domains
3. 输出最终 business_intents
4. 提取该接口的调用参数（params）
5. 输出 is_multi_domain 和 reasoning

规则：
- selected_api_id 必须来自候选列表
- query_domains 必须来自候选列表中的 domain，优先遵守轻量路由提示
- business_intents 不得输出前端动作名
- params 只包含选中接口 Schema 中定义的字段
- 直接输出 JSON，不要解释或包含 markdown

输出格式：
{{"selected_api_id":"...","query_domains":["crm"],"business_intents":["none"],"is_multi_domain":false,"reasoning":"...","params":{{}}}}"""




def _validate_params(params: dict[str, Any], entry: ApiCatalogEntry) -> dict[str, Any]:
    """对 LLM 提参结果执行 Schema 过滤与基础类型收敛。"""
    schema_props = entry.param_schema.properties
    if not schema_props:
        return params

    validated: dict[str, Any] = {}
    for key, value in params.items():
        if key not in schema_props:
            logger.debug("Filtered hallucinated param '%s' for %s", key, entry.id)
            continue
        prop_type = schema_props[key].get("type", "string")
        validated[key] = _coerce_type(value, prop_type)

    return validated


def _parse_json(raw_text: str) -> dict[str, Any]:
    """兼容旧测试/调用方的 JSON 解析入口。"""
    return parse_dirty_json_object(raw_text)


def _coerce_type(value: Any, expected_type: str) -> Any:
    """将常见字符串形态收敛到 Schema 要求的类型。"""
    try:
        if expected_type == "integer":
            return int(value)
        if expected_type == "number":
            return float(value)
        if expected_type == "boolean":
            if isinstance(value, str):
                return value.lower() in ("true", "1", "yes")
            return bool(value)
        return str(value) if expected_type == "string" else value
    except (ValueError, TypeError):
        return value


def _sanitize_route_domains(raw_domains: Any) -> list[str]:
    """清洗轻量路由返回的领域编码。

    功能：
        统一大小写和连接符风格，并把 `unknown` 留给 route 层作为失败信号处理。
    """
    if isinstance(raw_domains, str):
        candidates = [raw_domains]
    elif isinstance(raw_domains, list):
        candidates = [str(item) for item in raw_domains if item]
    else:
        candidates = []

    domains: list[str] = []
    for candidate in candidates:
        normalized = _normalize_domain_code(candidate)
        if not normalized or normalized == _UNKNOWN_DOMAIN:
            continue
        domains.append(normalized)
    return list(dict.fromkeys(domains))


def _sanitize_query_domains(
    raw_domains: Any,
    candidates: list[ApiCatalogSearchResult],
    fallback_domain: str,
) -> list[str]:
    """限制最终 `query_domains` 只能落在候选集域内。

    功能：
        避免模型把第一阶段未召回的陌生域重新塞回响应，破坏链路可解释性。
    """
    allowed = {_normalize_domain_code(candidate.entry.domain) for candidate in candidates if candidate.entry.domain}
    normalized_items = _sanitize_route_domains(raw_domains)
    normalized_fallback = _normalize_domain_code(fallback_domain)
    domains = [item for item in normalized_items if item in allowed]
    if normalized_fallback and normalized_fallback not in domains:
        domains.insert(0, normalized_fallback)
    return list(dict.fromkeys(domains))


def _sanitize_business_intents(
    raw_business_intents: Any,
    *,
    allowed: set[str] | None,
    fallback: list[str],
) -> list[str]:
    """对白名单外业务意图做交集清洗，纯读场景统一回落到 `none`。"""
    if isinstance(raw_business_intents, str):
        candidates = [raw_business_intents]
    elif isinstance(raw_business_intents, list):
        candidates = [str(item) for item in raw_business_intents if item]
    else:
        candidates = []

    candidates = [normalize_business_intent_code(item) for item in candidates]
    normalized_fallback = [normalize_business_intent_code(item) for item in fallback]

    if allowed is not None:
        candidates = [item for item in candidates if item in allowed]

    if not candidates:
        # 业务意图宁可回退到 `none`，也不能把模型臆造的写动作透传到下游。
        candidates = [item for item in normalized_fallback if allowed is None or item in allowed]

    return list(dict.fromkeys(candidates or [_NOOP_BUSINESS_INTENT]))


def _normalize_domain_code(raw_domain: str | None) -> str:
    """统一 domain 编码格式，避免大小写或连接符差异影响候选匹配。"""
    if raw_domain is None:
        return ""
    return raw_domain.strip().lower().replace("-", "_").replace(" ", "_")


def _safe_string(value: Any) -> str | None:
    """把模型的自由文本字段收敛成短字符串，避免把复杂对象混入日志与响应。"""
    if value is None:
        return None
    text = str(value).strip()
    return text or None
