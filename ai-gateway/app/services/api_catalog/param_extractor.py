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
from app.services.api_catalog.schema import ApiCatalogEntry, ApiCatalogSearchResult

logger = logging.getLogger(__name__)

_NOOP_BUSINESS_INTENT = "none"
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

    def __init__(self) -> None:
        self._llm = None

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
        result = await self._call_llm_json(prompt, scenario="route_query")
        if not result:
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
            params = await self._extract_params(query, entry, user_context)
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
        )

    async def _extract_params(
        self,
        query: str,
        entry: ApiCatalogEntry,
        user_context: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """单接口参数提取。

        这里复用同一套 JSON 调用治理，目的是让单候选路径也具备相同的抗脏输出能力。
        """
        prompt = _build_extract_only_prompt(query, entry, user_context)
        params = await self._call_llm_json(prompt, scenario="extract_params")
        return _validate_params(params, entry)

    async def _route_and_extract(
        self,
        query: str,
        candidates: list[ApiCatalogSearchResult],
        user_context: dict[str, Any] | None,
        *,
        allowed_business_intents: set[str] | None,
        routing_hints: ApiQueryRoutingResult | None,
    ) -> ApiQueryRoutingResult:
        """多候选场景下的接口路由与参数提取。

        功能：
            把“选哪个接口”和“提什么参数”绑定在一次结构化输出里，减少多次模型调用引入的漂移。
        """
        prompt = _build_route_and_extract_prompt(query, candidates, user_context, routing_hints)
        result = await self._call_llm_json(prompt, scenario="route_and_extract")
        if not result:
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
            logger.warning("LLM selected unknown api_id '%s', falling back to top candidate", selected_id)
            entry = candidates[0].entry

        query_domain_fallback = (
            routing_hints.query_domains[0]
            if routing_hints and routing_hints.query_domains
            else entry.domain
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
            is_multi_domain=bool(result.get("is_multi_domain")) or (
                bool(routing_hints.is_multi_domain) if routing_hints else False
            ),
            reasoning=_safe_string(result.get("reasoning")) or (routing_hints.reasoning if routing_hints else None),
            params=_validate_params(raw_params, entry),
        )

    async def _call_llm_json(self, prompt: str, *, scenario: str) -> dict[str, Any]:
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
                    "LLM %s failed on attempt %s/%s: %s",
                    scenario,
                    attempt + 1,
                    max_attempts,
                    exc,
                )
                continue

            parsed = _parse_json(raw)
            if parsed:
                return parsed

            logger.warning(
                "LLM %s returned non-json payload on attempt %s/%s",
                scenario,
                attempt + 1,
                max_attempts,
            )

        return {}


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
    ctx_str = json.dumps(user_context or {}, ensure_ascii=False)
    allowed_intents = sorted(allowed_business_intents or {_NOOP_BUSINESS_INTENT})
    intents_str = json.dumps(allowed_intents, ensure_ascii=False)
    return f"""你是企业级工作流引擎的第二阶段轻量路由器。

用户输入：{query}
用户上下文：{ctx_str}

任务：
1. 提取 query_domains，输出 1 到 N 个业务域编码，例如 crm、erp、iam、meeting_bi；如果无法判断则输出 ["unknown"]
2. 提取 business_intents；纯查询场景输出 ["none"]，只允许使用这些编码：{intents_str}
3. 输出 is_multi_domain
4. 用一句简短中文说明 reasoning

规则：
- query_domains 只输出领域编码，不要输出接口名
- business_intents 只描述业务意图，不要输出 remoteQuery / remoteMutation 等前端动作
- 直接输出 JSON，不要解释或包含 markdown

输出格式：
{{"query_domains":["crm"],"business_intents":["none"],"is_multi_domain":false,"reasoning":"..."}}"""


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


def _parse_json(raw: str) -> dict[str, Any]:
    """从 LLM 输出中尽量抠出首个 JSON 对象。

    功能：
        第二阶段最怕的不是模型答错，而是输出了一段“半礼貌半 JSON”的混合文本。
        这里先剥掉 markdown，再截取首尾大括号，尽量把脏文本还原成可解析对象。
    """
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and start < end:
        text = text[start : end + 1]

    try:
        result = json.loads(text)
        return result if isinstance(result, dict) else {}
    except json.JSONDecodeError:
        logger.debug("Failed to parse LLM JSON: %s", raw[:200])
        return {}


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
        normalized = candidate.strip().lower().replace("-", "_").replace(" ", "_")
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
    allowed = {candidate.entry.domain for candidate in candidates if candidate.entry.domain}
    if isinstance(raw_domains, str):
        items = [raw_domains]
    elif isinstance(raw_domains, list):
        items = [str(item) for item in raw_domains if item]
    else:
        items = []

    domains = [item for item in items if item in allowed]
    if fallback_domain and fallback_domain not in domains:
        domains.insert(0, fallback_domain)
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

    if allowed is not None:
        candidates = [item for item in candidates if item in allowed]

    if not candidates:
        # 业务意图宁可回退到 `none`，也不能把模型臆造的写动作透传到下游。
        candidates = [item for item in fallback if allowed is None or item in allowed]

    return list(dict.fromkeys(candidates or [_NOOP_BUSINESS_INTENT]))


def _safe_string(value: Any) -> str | None:
    """把模型的自由文本字段收敛成短字符串，避免把复杂对象混入日志与响应。"""
    if value is None:
        return None
    text = str(value).strip()
    return text or None
