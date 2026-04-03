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
from app.bi.meeting_bi.db.async_session import get_meeting_pool
from app.bi.meeting_bi.schemas.common import BIChartConfig
from app.bi.meeting_bi.services.chart_store import save_chart
from app.core.config import settings
from app.models.schemas import QueryDomain, Text2SQLResponse
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
    sql = re.sub(r"^```\w*\n?", "", sql.strip())
    sql = re.sub(r"\n?```$", "", sql)
    return sql.strip().rstrip(";")


def _serialize_value(value):
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
        series = [{"name": num_cols[0], "data": [{"name": categories[i], "value": _to_float(rows[i].get(num_cols[0]))} for i in range(len(rows))]}]
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
    try:
        answer = vn.submit_prompt(_RELEVANCE_PROMPT.format(question=question))
        return "是" in answer[:10]
    except Exception:  # pragma: no cover - runtime safety
        return True


def _validate_allowed_tables(sql: str) -> None:
    tables = {match.lower() for match in _TABLE_PATTERN.findall(sql)}
    disallowed = sorted(tables - _ALLOWED_TABLES)
    if disallowed:
        raise ValueError(f"检测到非会议 BI 白名单表：{', '.join(disallowed)}")


async def _execute_sql(sql: str) -> tuple[list[str], list[dict]]:
    """使用 aiomysql 执行 SQL，返回 (columns, rows)。"""
    pool = await get_meeting_pool()
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
    return [{k: (str(v) if v is not None and not isinstance(v, (int, float)) else v) for k, v in row.items()} for row in rows]


class MeetingBIQueryExecutor:
    """会议 BI 专用问数执行器 — aiomysql + SSE stream 支持。"""

    async def query(
        self,
        question: str,
        *,
        conversation_id: str | None = None,
        context: dict | None = None,
    ) -> Text2SQLResponse:
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
        sanitized_sql = GenericQueryExecutor._sanitize_sql(cleaned_sql, settings.meeting_bi_max_rows)
        _validate_allowed_tables(sanitized_sql)

        try:
            columns, rows = await _execute_sql(sanitized_sql)
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

        # 上下文改写
        rewritten = _rewrite_question(vn, question, conversation_id)

        # 意图判断
        if not await asyncio.to_thread(_is_relevant_question, vn, rewritten):
            yield _sse("answer", {"answer": _OUT_OF_SCOPE_ANSWER})
            return

        # 阶段 1: 生成 SQL
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

        # 阶段 2: 执行 SQL
        try:
            columns, rows = await _execute_sql(sanitized_sql)
            safe = _safe_rows(rows)
        except Exception as exc:
            logger.error("Meeting BI SQL execution failed: %s\nSQL: %s", exc, sanitized_sql)
            yield _sse("error", {"message": "抱歉，查询未能成功执行，请尝试换一种方式提问。"})
            return

        yield _sse("data", {"columns": columns, "rows": safe})

        # 阶段 3: 生成并保存图表
        chart = _build_chart(columns, rows)
        if chart:
            chart_id = await save_chart(chart)
            yield _sse("chart", {"chart": chart.model_dump(), "chart_id": chart_id})

        # 阶段 4: 生成自然语言回答
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
