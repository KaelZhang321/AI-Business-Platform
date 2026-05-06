"""智能订餐风险识别服务。"""

from __future__ import annotations

import json
import re
from typing import Any

import aiomysql
import httpx

from app.core.config import settings
from app.services.health_quadrant_mysql_pools import HealthQuadrantMySQLPools
from app.utils.text_utils import normalize_scalar_text as _normalize_text


_INTOLERANCE_ENDPOINT = f"{settings.dw_route_url.rstrip('/')}/food-intolerance-items"


class SmartMealRiskServiceError(RuntimeError):
    """智能订餐风险服务异常。"""


class SmartMealRiskService:
    """智能订餐风险识别服务。"""

    def __init__(
        self,
        *,
        mysql_pools: HealthQuadrantMySQLPools | None = None,
    ) -> None:
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

    async def identify_risks(
        self,
        *,
        id_card_no: str,
        campus_id: str,
        meal_snapshot: list[dict[str, str | None]],
        trace_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """执行智能订餐风险识别。"""

        if not campus_id.strip():
            raise SmartMealRiskServiceError("bad_request: campus_id 不能为空")
        normalized_snapshot = _normalize_meal_snapshot(meal_snapshot)
        if not normalized_snapshot:
            raise SmartMealRiskServiceError("bad_request: meal_snapshot 不能为空")

        intolerance_items = await self._fetch_intolerance_items(
            id_card_no=id_card_no,
            trace_id=trace_id,
        )
        if not intolerance_items:
            return []
        dish_rows = await self._query_meal_dishes(
            campus_id=campus_id,
            package_ingredients=normalized_snapshot,
        )
        if not dish_rows:
            return []

        risk_items = self._identify_risk_items_by_rule(
            intolerance_items=intolerance_items,
            dish_rows=dish_rows,
        )
        return self._normalize_risk_items(risk_items)

    async def _fetch_intolerance_items(
        self,
        *,
        id_card_no: str,
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

    def _identify_risk_items_by_rule(
        self,
        *,
        intolerance_items: list[str],
        dish_rows: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        intolerance_dict: dict[str, str] = {}
        for item in intolerance_items:
            ingredient, level = self._parse_intolerance_item(item)
            if not ingredient:
                continue
            if ingredient not in intolerance_dict:
                intolerance_dict[ingredient] = level
                continue
            if intolerance_dict[ingredient] == "未知" and level != "未知":
                intolerance_dict[ingredient] = level

        risk_items: list[dict[str, Any]] = []
        for row in dish_rows:
            dish_name = _normalize_text(row.get("dish_name"))
            dish_code = _normalize_text(row.get("dish_code"))
            if not dish_code:
                continue
            dish_terms = _extract_dish_terms(row.get("ingredient_json"))
            if not dish_terms:
                continue
            for intolerance_ingredient, level in intolerance_dict.items():
                matched = False
                for dish_term in dish_terms:
                    if not self._is_ingredient_match(
                        meal_ingredient=dish_term,
                        intolerance_ingredient=intolerance_ingredient,
                    ):
                        continue
                    risk_items.append(
                        {
                            "ingredient": intolerance_ingredient,
                            "intolerance_level": level,
                            "dish_code": dish_code,
                            "dish_name": dish_name,
                        }
                    )
                    matched = True
                    break
                if matched:
                    continue
        return risk_items

    def _normalize_risk_items(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        merged: dict[str, dict[str, Any]] = {}
        for item in items:
            ingredient = _normalize_text(item.get("ingredient"))
            if not ingredient:
                continue
            level = _normalize_text(item.get("intolerance_level")) or "未知"
            dishes = _normalize_risk_dishes(item)
            if ingredient not in merged:
                merged[ingredient] = {
                    "intolerance_level": level,
                    "dishes": dishes,
                }
            else:
                if merged[ingredient]["intolerance_level"] == "未知" and level != "未知":
                    merged[ingredient]["intolerance_level"] = level
                merged[ingredient]["dishes"] = _merge_dishes(merged[ingredient]["dishes"], dishes)

        normalized: list[dict[str, Any]] = []
        for ingredient in sorted(merged.keys()):
            normalized.append(
                {
                    "ingredient": ingredient,
                    "intolerance_level": merged[ingredient]["intolerance_level"],
                    "dishes": merged[ingredient]["dishes"],
                }
            )
        return normalized

    def _parse_intolerance_item(self, raw_item: str) -> tuple[str, str]:
        text = _normalize_text(raw_item)
        if not text:
            return "", "未知"

        columns = re.split(r"[：:]", text, maxsplit=1)
        ingredient = _clean_intolerance_ingredient(columns[0])
        level = _normalize_text(columns[1]) if len(columns) > 1 else ""
        return ingredient, (level or "未知")

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

    async def _query_meal_dishes(
        self,
        *,
        campus_id: str,
        package_ingredients: list[dict[str, str]],
    ) -> list[dict[str, Any]]:
        dish_codes = sorted(
            {
                _normalize_text(item.get("dish_code"))
                for item in package_ingredients
                if _normalize_text(item.get("dish_code"))
            }
        )
        if not dish_codes:
            return []

        placeholders = ", ".join(["%s"] * len(dish_codes))
        sql = f"""
            SELECT campus_id, dish_code, dish_name, ingredient_json
            FROM meal_dish
            WHERE deleted = 0
              AND campus_id = %s
              AND dish_code IN ({placeholders})
        """
        pool = await self._mysql_pools.get_ods_pool()
        params = [campus_id, *dish_codes]
        try:
            async with pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute(sql, params)
                    rows = await cursor.fetchall()
        except Exception as exc:
            raise SmartMealRiskServiceError("db_failed: 菜品食材查询失败") from exc
        if not isinstance(rows, list):
            return []
        return rows

def _normalize_meal_snapshot(meal_snapshot: list[dict[str, str | None]]) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    for item in meal_snapshot:
        dish_code = _normalize_text(item.get("dish_code"))
        if not dish_code:
            continue
        normalized.append(
            {
                "dish_code": dish_code,
                "dish_name": _normalize_text(item.get("dish_name")),
            }
        )
    return normalized

def _normalize_risk_dishes(item: dict[str, Any]) -> list[dict[str, str]]:
    raw_dishes = item.get("dishes")
    if isinstance(raw_dishes, list):
        normalized: list[dict[str, str]] = []
        for dish in raw_dishes:
            if not isinstance(dish, dict):
                continue
            dish_code = _normalize_text(dish.get("dish_code"))
            dish_name = _normalize_text(dish.get("dish_name"))
            if not dish_code and not dish_name:
                continue
            normalized.append({"dish_code": dish_code, "dish_name": dish_name})
        return normalized

    dish_code = _normalize_text(item.get("dish_code"))
    dish_name = _normalize_text(item.get("dish_name"))
    if not dish_code and not dish_name:
        return []
    return [{"dish_code": dish_code, "dish_name": dish_name}]


def _merge_dishes(left: list[dict[str, str]], right: list[dict[str, str]]) -> list[dict[str, str]]:
    dedup: dict[tuple[str, str], dict[str, str]] = {}
    for dish in left + right:
        dish_code = _normalize_text(dish.get("dish_code"))
        dish_name = _normalize_text(dish.get("dish_name"))
        if not dish_code and not dish_name:
            continue
        dedup[(dish_code, dish_name)] = {"dish_code": dish_code, "dish_name": dish_name}
    return [dedup[key] for key in sorted(dedup)]


def _clean_intolerance_ingredient(raw_ingredient: str) -> str:
    text = _normalize_text(raw_ingredient)
    if not text:
        return ""
    normalized = text.replace("特异性IgG抗体", "").replace("-sIgE抗体升高", "")
    normalized = re.sub(r"[\(（][^\)）]*[\)）]", "", normalized)
    normalized = normalized.replace("(", "").replace(")", "").replace("（", "").replace("）", "")
    return _normalize_text(normalized)


def _extract_dish_terms(raw_ingredient_json: Any) -> list[str]:
    payload = raw_ingredient_json
    if isinstance(payload, (bytes, bytearray)):
        payload = payload.decode("utf-8", errors="ignore")
    if isinstance(payload, str):
        payload = payload.strip()
        if not payload:
            return []
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return []
    if isinstance(payload, dict):
        payload = [payload]
    if not isinstance(payload, list):
        return []

    terms: list[str] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        ingredient_name = _pick_first_text(item, ("ingredientName", "ingredient_name", "ingredient", "name"))
        ingredient_category = _pick_first_text(
            item,
            (
                "ingredientCatagory",
                "ingredientCategory",
                "ingredient_catagory",
                "ingredient_category",
                "category",
            ),
        )
        if ingredient_name:
            terms.append(ingredient_name)
        if ingredient_category:
            terms.append(ingredient_category)
    # 保持顺序去重，避免同一食材项命中重复追加。
    dedup: list[str] = []
    seen: set[str] = set()
    for term in terms:
        lowered = term.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        dedup.append(term)
    return dedup


def _pick_first_text(payload: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = _normalize_text(payload.get(key))
        if value:
            return value
    return ""
