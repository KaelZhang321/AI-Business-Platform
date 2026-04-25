"""智能订餐风险识别服务。"""

from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from typing import Any

import aiomysql
import httpx

from app.core.config import settings
from app.services.health_quadrant_mysql_pools import HealthQuadrantMySQLPools
from app.services.smart_meal_llm_service import SmartMealLLMService
from app.utils.json_utils import parse_dirty_json_object

logger = logging.getLogger(__name__)

_INTOLERANCE_ENDPOINT = f"{settings.dw_route_url.rstrip('/')}/food-intolerance-items"
_INTOLERANCE_INGREDIENT_KEYS = (
    "ingredient",
    "ingredient_name",
    "ingredientName",
    "food_name",
    "foodName",
    "allergen",
    "allergenName",
    "item_name",
    "itemName",
    "name",
)
_INTOLERANCE_LEVEL_KEYS = (
    "intolerance_level",
    "intoleranceLevel",
    "level",
    "result_level",
    "resultLevel",
    "degree",
    "grade",
    "igg_level",
    "iggLevel",
)

_RISK_INGREDIENT_KEYS = ("ingredient", "ingredient_name", "ingredientName", "name")
_RISK_LEVEL_KEYS = ("intolerance_level", "intoleranceLevel", "level")
_RISK_SOURCE_DISH_KEYS = ("source_dish", "sourceDish", "dish_name", "dishName")


class SmartMealRiskServiceError(RuntimeError):
    """智能订餐风险服务异常。"""


class SmartMealRiskService:
    """智能订餐风险识别服务。"""

    def __init__(
        self,
        *,
        llm_service: SmartMealLLMService | None = None,
        mysql_pools: HealthQuadrantMySQLPools | None = None,
    ) -> None:
        self._llm_service = llm_service or SmartMealLLMService()
        self._http_client: httpx.AsyncClient | None = None
        self._mysql_pools = mysql_pools or HealthQuadrantMySQLPools(minsize=1, maxsize=3)
        self._owned_mysql_pools = mysql_pools is None

    async def warmup(self) -> None:
        """预热数据库连接池。"""

        await self._mysql_pools.get_business_pool()

    async def close(self) -> None:
        """关闭服务资源。"""

        if self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None

        if self._owned_mysql_pools:
            await self._mysql_pools.close()

        await self._llm_service.close()

    async def identify_risks(
        self,
        *,
        id_card_no: str,
        sex: str,
        age: int,
        package_code: str,
        trace_id: str | None = None,
    ) -> list[dict[str, str]]:
        """执行智能订餐风险识别。"""

        intolerance_items = await self._fetch_intolerance_items(
            id_card_no=id_card_no,
            sex=sex,
            age=age,
            trace_id=trace_id,
        )
        package_ingredients = await self._query_package_ingredients(package_code=package_code)
        if not package_ingredients:
            raise SmartMealRiskServiceError(f"package_not_found: 套餐不存在或无有效食材 package_code={package_code}")
        if not intolerance_items:
            return []

        llm_items = await self._identify_risk_items_with_llm(
            intolerance_items=intolerance_items,
            package_ingredients=package_ingredients,
            trace_id=trace_id,
        )
        if llm_items:
            return self._normalize_risk_items(llm_items)

        fallback_items = self._identify_risk_items_by_rule(
            intolerance_items=intolerance_items,
            package_ingredients=package_ingredients,
        )
        return self._normalize_risk_items(fallback_items)

    async def _fetch_intolerance_items(
        self,
        *,
        id_card_no: str,
        sex: str,
        age: int,
        trace_id: str | None = None,
    ) -> list[str]:
        client = self._get_http_client()
        params = {
            "idcard_no": id_card_no
        }
        headers: dict[str, str] = {}
        if trace_id:
            headers["X-Trace-Id"] = trace_id
        try:
            response = await client.get(_INTOLERANCE_ENDPOINT, params=params, headers=headers)
            response.raise_for_status()
            raw = response.json()
            return raw["rows"]
        except httpx.TimeoutException as exc:
            raise SmartMealRiskServiceError("external_timeout: 食物不耐受接口超时") from exc
        except Exception as exc:
            raise SmartMealRiskServiceError("external_failed: 食物不耐受接口调用失败") from exc

    async def _query_package_ingredients(self, *, package_code: str) -> list[dict[str, str]]:
        sql = """
            SELECT
                p.package_name AS package_name,
                p.package_type AS package_type,
                d.dish_name AS dish_name,
                d.dish_type AS dish_type,
                d.ingredient_json AS ingredient_json
            FROM meal_package AS p
            JOIN meal_package_dish_binding AS db ON p.id = db.package_id
            JOIN meal_dish AS d ON db.dish_id = d.id
            WHERE p.package_code = %s
              AND p.status = 1
              AND db.status = 1
              AND d.status = 1
        """
        pool = await self._mysql_pools.get_ods_pool()
        try:
            async with pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute(sql, (package_code,))
                    rows = await cursor.fetchall()
        except Exception as exc:
            raise SmartMealRiskServiceError("db_failed: 套餐食材查询失败") from exc

        normalized_rows: list[dict[str, str]] = []
        for row in rows:
            dish_name = _normalize_text(row.get("dish_name"))
            if not dish_name:
                continue
            normalized_rows.extend(_extract_dish_ingredients(dish_name=dish_name, ingredient_json=row.get("ingredient_json")))
        return normalized_rows

    async def _identify_risk_items_with_llm(
        self,
        *,
        intolerance_items: list[str],
        package_ingredients: list[dict[str, str]],
        trace_id: str | None = None,
    ) -> list[dict[str, str]]:
        meal_text = self._build_meal_text(package_ingredients)
        intolerance_text = self._build_intolerance_text(intolerance_items)
        prompt = self._build_llm_prompt(meal_text=meal_text, intolerance_text=intolerance_text)
        try:
            raw = await self._llm_service.chat(
                messages=[
                    {
                        "role": "system",
                        "content": "你是高净值健康管理系统的核心临床营养风控引擎，请严格输出 JSON。",
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                temperature=0.1,
                response_format={"type": "json_object"},
                timeout_seconds=45.0,
            )
        except Exception as exc:
            logger.warning("smart meal risk llm failed trace_id=%s error=%r", trace_id, exc)
            return []

        payload = parse_dirty_json_object(raw)
        if not payload:
            return []
        return self._extract_risk_items(payload)

    def _identify_risk_items_by_rule(
        self,
        *,
        intolerance_items: list[str],
        package_ingredients: list[dict[str, str]],
    ) -> list[dict[str, str]]:
        intolerance_index: list[tuple[str, str]] = []
        for item in intolerance_items:
            ingredient, level = self._parse_intolerance_item(item)
            if ingredient:
                intolerance_index.append((ingredient, level))

        risk_items: list[dict[str, str]] = []
        for row in package_ingredients:
            dish_name = _normalize_text(row.get("dish_name"))
            ingredient_name = _normalize_text(row.get("ingredient_name"))
            if not dish_name or not ingredient_name:
                continue
            for intolerance_ingredient, level in intolerance_index:
                if self._is_ingredient_match(
                    meal_ingredient=ingredient_name,
                    intolerance_ingredient=intolerance_ingredient,
                ):
                    risk_items.append(
                        {
                            "ingredient": intolerance_ingredient,
                            "intolerance_level": level,
                            "source_dish": dish_name,
                        }
                    )
        return risk_items

    def _extract_risk_items(self, payload: dict[str, Any]) -> list[dict[str, str]]:
        result: list[dict[str, str]] = []

        def _walk(node: Any) -> None:
            if isinstance(node, dict):
                ingredient = _pick_first_text(node, _RISK_INGREDIENT_KEYS)
                source_dish = _pick_first_text(node, _RISK_SOURCE_DISH_KEYS)
                if ingredient and source_dish:
                    result.append(
                        {
                            "ingredient": ingredient,
                            "intolerance_level": _pick_first_text(node, _RISK_LEVEL_KEYS) or "未知",
                            "source_dish": source_dish,
                        }
                    )
                for value in node.values():
                    _walk(value)
            elif isinstance(node, list):
                for item in node:
                    _walk(item)

        _walk(payload)
        return result

    def _normalize_risk_items(self, items: list[dict[str, str]]) -> list[dict[str, str]]:
        merged: dict[str, dict[str, Any]] = {}
        for item in items:
            ingredient = _normalize_text(item.get("ingredient"))
            if not ingredient:
                continue
            level = _normalize_text(item.get("intolerance_level")) or "未知"
            dish_names = _split_source_dishes(item.get("source_dish"))
            if ingredient not in merged:
                merged[ingredient] = {
                    "intolerance_level": level,
                    "source_dish_set": set(dish_names),
                }
            else:
                if merged[ingredient]["intolerance_level"] == "未知" and level != "未知":
                    merged[ingredient]["intolerance_level"] = level
                merged[ingredient]["source_dish_set"].update(dish_names)

        normalized: list[dict[str, str]] = []
        for ingredient in sorted(merged.keys()):
            source_dish_set = merged[ingredient]["source_dish_set"]
            source_dish = "，".join(sorted(source_dish_set))
            normalized.append(
                {
                    "ingredient": ingredient,
                    "intolerance_level": merged[ingredient]["intolerance_level"],
                    "source_dish": source_dish,
                }
            )
        return normalized

    def _build_meal_text(self, package_ingredients: list[dict[str, str]]) -> str:
        dishes: dict[str, list[str]] = defaultdict(list)
        for row in package_ingredients:
            dish_name = _normalize_text(row.get("dish_name"))
            ingredient_name = _normalize_text(row.get("ingredient_name"))
            if dish_name and ingredient_name:
                dishes[dish_name].append(ingredient_name)
        lines = []
        for dish_name in sorted(dishes.keys()):
            ingredients = "、".join(sorted(set(dishes[dish_name])))
            lines.append(f"{dish_name}：{ingredients}")
        return "\n".join(lines)

    def _build_intolerance_text(self, intolerance_items: list[str]) -> str:
        lines = []
        for item in intolerance_items:
            ingredient, level = self._parse_intolerance_item(item)
            if ingredient:
                lines.append(f"{ingredient}（{level}）" if level != "未知" else ingredient)
        return "\n".join(lines)

    def _parse_intolerance_item(self, raw_item: str) -> tuple[str, str]:
        text = _normalize_text(raw_item)
        if not text:
            return "", "未知"

        match = re.match(r"^(?P<ingredient>.+?)[（(](?P<level>[^()（）]+)[)）]\s*$", text)
        if match:
            ingredient = _normalize_text(match.group("ingredient"))
            level = _normalize_text(match.group("level")) or "未知"
            return ingredient, level

        for sep in ("：", ":", "|", "｜", ";", "；", ",", "，"):
            if sep not in text:
                continue
            left, right = text.split(sep, 1)
            ingredient = _normalize_text(left)
            level = _normalize_text(right)
            if ingredient:
                if level and ("级" in level or "igg" in level.lower() or "level" in level.lower()):
                    return ingredient, level
                return ingredient, "未知"

        return text, "未知"

    def _build_llm_prompt(self, *, meal_text: str, intolerance_text: str) -> str:
        return (f"""
            # Task
            请分析【餐食描述文本】，并与该客户的【食物不耐受清单】进行严格比对，精准识别出这顿餐食中是否含有客户不耐受的食材，并以严格的 JSON 格式输出。
            
            # Workflow & Rules
            1. 深度语义拆解（关键步骤）：
               - 提取文本中直接写明的食材（如“炒西兰花”提取“西兰花”）。
               - 依靠烹饪常识，推理并拆解复杂菜名中必定或极大概率包含的“隐性辅料”（例如：看到“意大利面”必须拆解出“小麦/麸质”；看到“红烧肉”必须考虑到“酱油/大豆、糖”；看到“沙拉酱”需考虑“鸡蛋、大豆油”等）。
            2. 交叉比对：将拆解出的所有明线与暗线食材，与【食物不耐受清单】进行逐一精确核对。
            3. 提取分级：如果命中不耐受食材，必须从报告中准确提取其对应的具体级别（如：“1级”、“2级”或“IgG抗体3级”等）。
            4. 绝对去重：同一种不耐受食材如果在多个菜品中出现，在输出的风险清单中只保留一项，并在 source_dish 中用逗号合并菜名。
            5. 格式约束：仅输出合法的 JSON 字符串，禁止输出任何 Markdown 格式（严禁包含 ```json 标签）或前言后语。
            
            # Output JSON Schema
            {{
              "reasoning": "推理过程：1. 列出你从餐食文本中拆解出的所有显性与隐性食材；2. 说明哪些食材命中了不耐受清单及原因。",
              "has_risk": true, 
              "risk_items": [
                {{
                  "ingredient": "具体的食材名称（如：西兰花）",
                  "intolerance_level": "不耐受级别（如：1级）",
                  "source_dish": "该食材来源于哪道菜（如：蒜蓉西兰花）"
                }}
              ],
              "dietary_advice": "针对这顿餐食，给客户的一句话专业健康替换建议（无风险则给予鼓励）"
            }}
            
            # Inputs
            餐食描述文本：\n{meal_text}\n\n
            食物不耐受清单：\n{intolerance_text}\n
        """)

    def _is_ingredient_match(self, *, meal_ingredient: str, intolerance_ingredient: str) -> bool:
        left = meal_ingredient.strip().lower()
        right = intolerance_ingredient.strip().lower()
        if not left or not right:
            return False
        if left == right:
            return True
        if len(right) >= 2 and right in left:
            return True
        if len(left) >= 2 and left in right:
            return True
        return False

    def _get_http_client(self) -> httpx.AsyncClient:
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=15.0)
        return self._http_client

def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        return str(value).strip()
    if isinstance(value, str):
        return value.strip()
    return ""


def _pick_first_text(data: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = _normalize_text(data.get(key))
        if value:
            return value
    return ""


def _split_source_dishes(raw: str | None) -> set[str]:
    text = _normalize_text(raw)
    if not text:
        return set()
    normalized = text
    for sep in ("，", ",", "、", ";", "；", "|", "/"):
        normalized = normalized.replace(sep, ",")
    return {part.strip() for part in normalized.split(",") if part.strip()}


def _extract_dish_ingredients(*, dish_name: str, ingredient_json: Any) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for ingredient in _parse_ingredient_json(ingredient_json):
        ingredient_name = _pick_first_text(ingredient, ("ingredientName", "ingredient_name", "ingredient", "name"))
        ingredient_category = _pick_first_text(
            ingredient,
            ("ingredientCategory", "ingredient_category", "category", "ingredientType", "ingredient_type"),
        )
        if not ingredient_name:
            continue
        rows.append(
            {
                "dish_name": dish_name,
                "ingredient_name": ingredient_name,
                "ingredient_category": ingredient_category,
            }
        )
    return rows


def _parse_ingredient_json(raw_value: Any) -> list[dict[str, Any]]:
    value = raw_value
    if isinstance(value, (bytes, bytearray)):
        value = value.decode("utf-8", errors="ignore")
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        try:
            value = json.loads(text)
        except json.JSONDecodeError:
            return []
    if isinstance(value, dict):
        value = [value]
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]
