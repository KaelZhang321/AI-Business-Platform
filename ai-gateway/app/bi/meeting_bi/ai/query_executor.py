"""会议 BI 垂直问数执行器。

该模块把“问题改写 -> 域相关性判断 -> SQL 生成 -> 白名单校验 -> 执行 -> 结果回答”
收敛在一个独立链路里，避免垂直业务规则污染平台通用问数逻辑。
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import date, datetime
from decimal import Decimal
from typing import AsyncGenerator

import aiomysql

from app.bi.meeting_bi.ai.context_store import QARound, get_last_question, get_recent_rounds, save_round
from app.bi.meeting_bi.ai.training_data import TABLES
from app.bi.meeting_bi.ai.vanna_client import get_vanna
from app.bi.meeting_bi.schemas.common import BIChartConfig
from app.bi.meeting_bi.services.chart_store import save_chart
from app.core.config import settings
from app.models.schemas.text2sql import (
    QueryDomain,
    Text2SQLResponse,
)
from app.services.generic_query_executor import GenericQueryExecutor

logger = logging.getLogger(__name__)

_TABLE_PATTERN = re.compile(r"\b(?:from|join)\s+([a-zA-Z_][\w]*)", re.IGNORECASE)
_ALLOWED_TABLES = {table.lower() for table in TABLES}
_RELEVANCE_PROMPT = """你是一个会议BI数据分析助手，只能回答与会议 BI 数据表相关的问题。
用户问题：{question}
如果问题与会议 BI 无关，只回答"否"；相关则回答"是"。
"""
_OUT_OF_SCOPE_ANSWER = (
    "抱歉，我是会议 BI 数据分析助手，只能回答与会议报名、签到、客户画像、成交数据、运营统计等相关的问题。"
)


def _clean_sql(sql: str) -> str:
    """剥离模型常见的 markdown 包裹和结尾分号。"""
    sql = re.sub(r"^```\w*\n?", "", sql.strip())
    sql = re.sub(r"\n?```$", "", sql)
    return sql.strip().rstrip(";")


def _serialize_value(value):
    """把数据库原生类型转换成可 JSON 序列化的安全值。"""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return str(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _to_float(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _build_chart(columns: list[str], rows: list[dict]) -> BIChartConfig | None:
    """基于查询结果自动推断一个轻量 BI 图表。"""
    if not rows or len(rows) < 2 or len(columns) < 2:
        return None

    str_cols: list[str] = []
    num_cols: list[str] = []
    for col in columns:
        values = [r.get(col) for r in rows[:10] if r.get(col) is not None]
        if not values:
            continue
        is_num = all(isinstance(v, (int, float, Decimal)) or (isinstance(v, str) and _is_numeric(v)) for v in values)
        if is_num:
            num_cols.append(col)
        else:
            str_cols.append(col)

    if not str_cols or not num_cols:
        return None

    cat_col = str_cols[0]
    categories = [str(r.get(cat_col, "")) for r in rows]
    if len(num_cols) == 1 and len(rows) <= 8:
        series = [
            {
                "name": num_cols[0],
                "data": [
                    {"name": categories[i], "value": _to_float(rows[i].get(num_cols[0]))} for i in range(len(rows))
                ],
            }
        ]
        return BIChartConfig(chart_type="pie", categories=categories, series=series)
    if len(num_cols) == 1:
        series = [{"name": num_cols[0], "data": [_to_float(r.get(num_cols[0])) for r in rows]}]
        chart_type = "horizontal_bar" if len(rows) > 6 else "bar"
        return BIChartConfig(chart_type=chart_type, categories=categories, series=series)

    series = [{"name": col, "data": [_to_float(r.get(col)) for r in rows]} for col in num_cols[:4]]
    return BIChartConfig(chart_type="grouped_bar", categories=categories, series=series)


def _is_numeric(value: str) -> bool:
    try:
        float(value)
        return True
    except ValueError:
        return False


def _rewrite_question(vn, question: str, conversation_id: str | None) -> str:
    """结合最近一轮会话改写追问，提升指代类问题的 SQL 命中率。"""
    if not conversation_id:
        return question
    last_q = get_last_question(conversation_id)
    if not last_q:
        return question
    try:
        rewritten = vn.generate_rewritten_question(last_q, question)
        if rewritten and rewritten.strip():
            return rewritten.strip()
    except Exception as exc:  # pragma: no cover - runtime safety
        logger.warning("Meeting BI question rewrite failed, using original: %s", exc)
    return question


def _build_history_prompt(conversation_id: str | None) -> str:
    """构造回答阶段使用的最近会话摘要。"""
    if not conversation_id:
        return ""
    rounds = get_recent_rounds(conversation_id, n=2)
    if not rounds:
        return ""
    lines: list[str] = []
    for round_item in rounds:
        lines.append(f"Q: {round_item.rewritten}")
        if round_item.answer:
            lines.append(f"A: {round_item.answer[:200]}")
    return "历史对话：\n" + "\n".join(lines) + "\n\n"


def _is_relevant_question(vn, question: str) -> bool:
    """判断用户问题是否属于会议 BI 域。"""
    try:
        answer = vn.submit_prompt(_RELEVANCE_PROMPT.format(question=question))
        return "是" in answer[:10]
    except Exception:  # pragma: no cover - runtime safety
        return True


def _validate_allowed_tables(sql: str) -> None:
    """确保 SQL 只访问会议 BI 白名单表。"""
    tables = {match.lower() for match in _TABLE_PATTERN.findall(sql)}
    disallowed = sorted(tables - _ALLOWED_TABLES)
    if disallowed:
        raise ValueError(f"检测到非会议 BI 白名单表：{', '.join(disallowed)}")


async def _execute_sql(pool: aiomysql.Pool, sql: str) -> tuple[list[str], list[dict]]:
    """执行会议 BI SQL，并返回列信息与序列化后的行数据。"""
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await asyncio.wait_for(cur.execute(sql), timeout=settings.meeting_bi_max_rows or 30)
            raw_rows = await cur.fetchall()
            if not raw_rows:
                return [], []
            columns = list(raw_rows[0].keys())
            rows = [{col: _serialize_value(val) for col, val in row.items()} for row in raw_rows]
            return columns, rows


def _safe_rows(rows: list[dict]) -> list[dict]:
    """把复杂类型收敛成前端更易消费的轻量值。"""
    return [
        {k: (str(v) if v is not None and not isinstance(v, (int, float)) else v) for k, v in row.items()}
        for row in rows
    ]


class MeetingBIQueryExecutor:
    """会议 BI 专用问数执行器。

    功能：
        负责承载会议 BI 垂直知识、白名单安全和图表回答能力，与通用 Text2SQL 执行器解耦。

    Edge Cases:
        - 域外问题直接返回拒答文案，不走 SQL 生成
        - SQL 生成成功后仍要经过只读与白名单双重校验
    """

    def __init__(self, *, pool: aiomysql.Pool) -> None:
        self._pool = pool

    async def query(
        self,
        question: str,
        *,
        conversation_id: str | None = None,
        context: dict | None = None,
    ) -> Text2SQLResponse:
        """同步执行会议 BI 问数。

        Args:
            question: 用户自然语言问题。
            conversation_id: 会话 ID，用于多轮追问改写。
            context: 预留上下文字段，当前会议 BI 链路未使用。

        Returns:
            标准 `Text2SQLResponse`，包含回答、SQL、表格结果和可选图表。
        """
        del context
        vn = await asyncio.to_thread(get_vanna)
        rewritten = _rewrite_question(vn, question, conversation_id)

        if not _is_relevant_question(vn, rewritten):
            return Text2SQLResponse(
                sql="",
                explanation="会议 BI 问数域外问题",
                domain=QueryDomain.MEETING_BI,
                answer=_OUT_OF_SCOPE_ANSWER,
                results=[],
                chart_spec=None,
            )

        try:
            sql = await asyncio.to_thread(vn.generate_sql, rewritten)
        except Exception as exc:  # pragma: no cover - runtime safety
            logger.error("Meeting BI SQL generation failed: %s", exc)
            raise ValueError("会议 BI SQL 生成失败，请尝试换一种方式提问") from exc

        cleaned_sql = _clean_sql(sql or "")
        # 先复用平台统一 SQL 安全闸门，再叠加会议 BI 白名单表限制。
        sanitized_sql = GenericQueryExecutor._sanitize_sql(cleaned_sql, settings.meeting_bi_max_rows)
        _validate_allowed_tables(sanitized_sql)

        try:
            columns, rows = await _execute_sql(self._pool, sanitized_sql)
        except Exception as exc:  # pragma: no cover - runtime safety
            logger.error("Meeting BI SQL execution failed: %s\nSQL: %s", exc, sanitized_sql)
            raise ValueError("会议 BI 查询执行失败，请稍后重试") from exc

        chart = _build_chart(columns, rows)
        chart_id: str | None = None
        if chart:
            chart_id = await save_chart(chart)

        display_rows = rows[:30]
        history_prompt = _build_history_prompt(conversation_id)
        try:
            answer_prompt = (
                f"{history_prompt}"
                f"用户问题：{rewritten}\nSQL：{sanitized_sql}\n结果（共{len(rows)}行）：{display_rows}\n\n"
                "请用简洁中文回答，直接给出关键数据和结论。"
            )
            answer = await asyncio.to_thread(vn.submit_prompt, [{"role": "user", "content": answer_prompt}])
        except Exception:  # pragma: no cover - runtime safety
            answer = f"查询成功，共返回 {len(rows)} 条数据。"

        if conversation_id:
            save_round(
                conversation_id,
                QARound(
                    question=question,
                    rewritten=rewritten,
                    sql=sanitized_sql,
                    answer=answer[:200] if answer else "",
                ),
            )

        chart_spec = chart.model_dump() if chart else None
        if chart_spec and chart_id:
            chart_spec["chart_id"] = chart_id

        return Text2SQLResponse(
            sql=sanitized_sql,
            explanation="会议 BI 问数执行完成",
            domain=QueryDomain.MEETING_BI,
            answer=answer,
            results=_safe_rows(rows),
            chart_spec=chart_spec,
        )

    async def stream(
        self,
        question: str,
        *,
        conversation_id: str | None = None,
    ) -> AsyncGenerator[dict, None]:
        """
        SSE 流式执行 AI 查询，分4阶段 yield 事件::

            event: sql     {"sql": "..."}
            event: data    {"columns": [...], "rows": [...]}
            event: chart   {"chart": {...}, "chart_id": "abc123"}
            event: answer  {"answer": "..."}
            event: error   {"message": "..."}
        """

        def _sse(event: str, data: dict) -> dict:
            return {"event": event, "data": json.dumps(data, ensure_ascii=False)}

        # 初始化 Vanna
        try:
            vn = await asyncio.to_thread(get_vanna)
        except Exception as exc:
            logger.error("Vanna init failed: %s", exc)
            yield _sse("error", {"message": "AI 服务暂时不可用，请稍后再试。"})
            return

        # 1. 先做追问改写，避免“这个大区”“刚才那个指标”之类指代在 SQL 阶段丢失上下文。
        rewritten = _rewrite_question(vn, question, conversation_id)

        # 2. 域外问题尽早返回，避免无意义地生成 SQL。
        if not await asyncio.to_thread(_is_relevant_question, vn, rewritten):
            yield _sse("answer", {"answer": _OUT_OF_SCOPE_ANSWER})
            return

        # 3. 生成 SQL 后仍要经过平台只读校验和会议 BI 白名单校验。
        try:
            sql = await asyncio.to_thread(vn.generate_sql, rewritten)
            if not sql:
                yield _sse("error", {"message": "无法生成 SQL，请尝试更具体的描述。"})
                return
            sql = _clean_sql(sql)
            sanitized_sql = GenericQueryExecutor._sanitize_sql(sql, settings.meeting_bi_max_rows)
            _validate_allowed_tables(sanitized_sql)
        except ValueError as exc:
            yield _sse("error", {"message": str(exc)})
            return
        except Exception as exc:
            logger.error("Meeting BI SQL generation failed: %s", exc)
            yield _sse("error", {"message": "抱歉，我暂时无法理解这个问题，请换一种方式描述再试试。"})
            return

        yield _sse("sql", {"sql": sanitized_sql})

        # 4. SQL 执行与结果回传分离，便于前端先看到结构化数据，再等待图表和总结。
        try:
            columns, rows = await _execute_sql(self._pool, sanitized_sql)
            safe = _safe_rows(rows)
        except Exception as exc:
            logger.error("Meeting BI SQL execution failed: %s\nSQL: %s", exc, sanitized_sql)
            yield _sse("error", {"message": "抱歉，查询未能成功执行，请尝试换一种方式提问。"})
            return

        yield _sse("data", {"columns": columns, "rows": safe})

        # 5. 图表是增强项，失败不应影响表格与自然语言结果。
        chart = _build_chart(columns, rows)
        if chart:
            chart_id = await save_chart(chart)
            yield _sse("chart", {"chart": chart.model_dump(), "chart_id": chart_id})

        # 6. 最后生成自然语言总结，确保回答基于已执行的真实结果而不是凭空生成。
        try:
            display_rows = rows[:30]
            history_prompt = _build_history_prompt(conversation_id)
            answer_prompt = (
                f"{history_prompt}"
                f"用户问题：{rewritten}\nSQL：{sanitized_sql}\n结果（共{len(rows)}行）：{display_rows}\n\n"
                "请用简洁中文回答，直接给出关键数据和结论。"
            )
            answer = await asyncio.to_thread(vn.submit_prompt, [{"role": "user", "content": answer_prompt}])
        except Exception:  # pragma: no cover - runtime safety
            answer = f"查询成功，共返回 {len(rows)} 条数据。"

        if conversation_id:
            save_round(
                conversation_id,
                QARound(
                    question=question,
                    rewritten=rewritten,
                    sql=sanitized_sql,
                    answer=answer[:200] if answer else "",
                ),
            )

        yield _sse("answer", {"answer": answer})
