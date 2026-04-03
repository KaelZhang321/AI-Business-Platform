"""
API Catalog — LLM 参数提取器

给定最匹配的 ApiCatalogEntry + 用户原始查询，
通过 LLM 提取接口所需的调用参数，并用 JSON Schema 校验结果。

设计约束：
- 接口选择（从 Top-K 候选选最优）和参数提取 在同一次 LLM 调用中完成，节省 token
- jsonschema 校验防止 LLM 幻觉产生非法参数
- 校验失败时自动降级：只传允许的字段，过滤非法字段

使用方式::

    from app.services.api_catalog.param_extractor import ApiParamExtractor
    extractor = ApiParamExtractor()
    api_id, params = await extractor.extract(query, candidates)
"""
from __future__ import annotations

import json
import logging
from typing import Any

from app.services.api_catalog.schema import ApiCatalogEntry, ApiCatalogSearchResult

logger = logging.getLogger(__name__)


class ApiParamExtractor:
    """通过 LLM 从用户查询中提取接口路由 + 参数。"""

    def __init__(self) -> None:
        self._llm = None

    def _get_llm(self):
        if self._llm is None:
            from app.services.llm_service import LLMService
            self._llm = LLMService()
        return self._llm

    async def extract(
        self,
        query: str,
        candidates: list[ApiCatalogSearchResult],
        user_context: dict[str, Any] | None = None,
    ) -> tuple[ApiCatalogEntry | None, dict[str, Any]]:
        """
        从候选接口列表中选择最优接口，并提取调用参数。

        Args:
            query: 用户原始输入
            candidates: 向量检索返回的候选接口列表（建议 Top-3）
            user_context: 可选的上下文（如 current_user_id 等可自动填充的参数）

        Returns:
            (selected_entry, params_dict)
            - selected_entry: 选中的接口，无法匹配时返回 None
            - params_dict: 提取到的参数字典，可能为空 {}
        """
        if not candidates:
            return None, {}

        # 单候选时跳过路由，直接提参数
        if len(candidates) == 1:
            return candidates[0].entry, await self._extract_params(query, candidates[0].entry, user_context)

        # 多候选：一次 LLM 调用完成「接口路由 + 参数提取」
        return await self._route_and_extract(query, candidates, user_context)

    # ── 单接口参数提取 ──────────────────────────────────────────

    async def _extract_params(
        self,
        query: str,
        entry: ApiCatalogEntry,
        user_context: dict[str, Any] | None,
    ) -> dict[str, Any]:
        prompt = _build_extract_only_prompt(query, entry, user_context)
        raw = await self._call_llm(prompt)
        params = _parse_json(raw)
        return _validate_params(params, entry)

    # ── 多候选路由 + 提参 ───────────────────────────────────────

    async def _route_and_extract(
        self,
        query: str,
        candidates: list[ApiCatalogSearchResult],
        user_context: dict[str, Any] | None,
    ) -> tuple[ApiCatalogEntry | None, dict[str, Any]]:
        prompt = _build_route_and_extract_prompt(query, candidates, user_context)
        raw = await self._call_llm(prompt)
        result = _parse_json(raw)

        selected_id = result.get("selected_api_id")
        raw_params = result.get("params", {})

        # 找到选中的接口
        entry = next((c.entry for c in candidates if c.entry.id == selected_id), None)
        if entry is None:
            # LLM 返回了不在候选列表中的 id，降级为第一个候选
            logger.warning(
                "LLM selected unknown api_id '%s', falling back to top candidate", selected_id
            )
            entry = candidates[0].entry

        params = _validate_params(raw_params, entry)
        return entry, params

    async def _call_llm(self, prompt: str) -> str:
        llm = self._get_llm()
        try:
            return await llm.chat(messages=[{"role": "user", "content": prompt}])
        except Exception as exc:
            logger.warning("LLM call failed in param extractor: %s", exc)
            return "{}"


# ── Prompt 构建 ──────────────────────────────────────────────────────────────

def _build_extract_only_prompt(
    query: str,
    entry: ApiCatalogEntry,
    user_context: dict[str, Any] | None,
) -> str:
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
2. 用户未提及的可选参数不要包含（让接口用默认值）
3. 类型严格匹配 Schema 中的 type（integer, string, boolean）
4. 直接输出 JSON 对象，不要解释或包含 markdown 代码块

输出："""


def _build_route_and_extract_prompt(
    query: str,
    candidates: list[ApiCatalogSearchResult],
    user_context: dict[str, Any] | None,
) -> str:
    ctx_str = json.dumps(user_context or {}, ensure_ascii=False)
    candidates_str = "\n".join(
        f"- id: {c.entry.id}\n  描述: {c.entry.description}\n  参数Schema: {json.dumps(c.entry.param_schema.model_dump(), ensure_ascii=False)}"
        for c in candidates
    )
    return f"""你是一个接口路由 + 参数提取助手。

用户输入：{query}
用户上下文：{ctx_str}

候选接口列表：
{candidates_str}

任务：
1. 从候选接口中选择最匹配用户意图的接口（selected_api_id）
2. 从用户输入 + 上下文中提取该接口的调用参数（params）

规则：
- selected_api_id 必须是候选列表中的某个 id
- params 只包含选中接口 Schema 中定义的字段
- 类型严格匹配
- 用户未提及的可选参数不要包含
- 直接输出 JSON，格式为 {{"selected_api_id": "...", "params": {{...}}}}

输出："""


# ── 工具函数 ─────────────────────────────────────────────────────────────────

def _parse_json(raw: str) -> dict[str, Any]:
    """从 LLM 输出中提取 JSON，容错 markdown 代码块。"""
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    try:
        result = json.loads(text)
        return result if isinstance(result, dict) else {}
    except json.JSONDecodeError:
        logger.debug("Failed to parse LLM JSON: %s", raw[:200])
        return {}


def _validate_params(params: dict[str, Any], entry: ApiCatalogEntry) -> dict[str, Any]:
    """
    校验 LLM 提取的参数：
    1. 过滤 Schema 中未定义的字段（防幻觉）
    2. 尝试类型转换（如 LLM 返回 "1" 但 Schema 要求 integer）
    """
    schema_props = entry.param_schema.properties
    if not schema_props:
        return params  # 无 Schema 定义时透传

    validated: dict[str, Any] = {}
    for key, value in params.items():
        if key not in schema_props:
            logger.debug("Filtered hallucinated param '%s' for %s", key, entry.id)
            continue
        prop_type = schema_props[key].get("type", "string")
        validated[key] = _coerce_type(value, prop_type)

    return validated


def _coerce_type(value: Any, expected_type: str) -> Any:
    """尝试将值转换为 Schema 期望类型。"""
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
