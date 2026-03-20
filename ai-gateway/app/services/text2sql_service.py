from __future__ import annotations

import asyncio
import json
import re

import asyncpg

from app.core.config import settings
from app.models.schemas import Text2SQLResponse
from app.services.dynamic_ui_service import DynamicUIService

_SQL_WRITE_OPERATORS = re.compile(
    r"\b(insert|update|delete|drop|alter|create|grant|revoke|truncate|call|merge)\b",
    re.IGNORECASE,
)


class Text2SQLService:
    """Text2SQL服务 — 基于 Vanna.ai 2.0+

    流程:
    1. 训练：导入数据库 Schema + 样例问答对
    2. 推理：自然语言 → SQL
    3. 执行：安全 SQL 执行
    4. 渲染：结果转 JSON Spec
    """

    def __init__(self):
        self._vn = None
        self._dynamic_ui = DynamicUIService()

    def _get_vanna(self):
        """懒加载 Vanna 实例"""
        if self._vn is None:
            from vanna.ollama import Ollama
            from vanna.milvus import Milvus_VectorStore

            class VannaOllama(Milvus_VectorStore, Ollama):
                def __init__(self, config=None):
                    Milvus_VectorStore.__init__(self, config=config)
                    Ollama.__init__(self, config=config)

            self._vn = VannaOllama(config={
                "model": "qwen2.5:7b",
                "ollama_host": settings.ollama_base_url,
            })
        return self._vn

    async def query(self, question: str, database: str = "default") -> Text2SQLResponse:
        """将自然语言问题转为SQL并执行"""
        vn = self._get_vanna()
        sql = vn.ask(question)
        sanitized_sql = self._sanitize_sql(sql)
        rows = await self._execute_sql(sanitized_sql, database)
        ui_spec = await self._dynamic_ui.generate_ui_spec("query", rows, {"question": question})
        return Text2SQLResponse(
            sql=sanitized_sql,
            explanation=f'自然语言问题 "{question}" 转为 SQL 并执行',
            results=rows,
            chart_spec=ui_spec,
        )

    async def _execute_sql(self, sql: str, database: str) -> list[dict]:
        conn = await asyncpg.connect(dsn=settings.database_url)
        try:
            records = await asyncio.wait_for(
                conn.fetch(sql),
                timeout=settings.text2sql_timeout_seconds,
            )
            return [dict(record) for record in records]
        finally:
            await conn.close()

    def _sanitize_sql(self, sql: str) -> str:
        if not sql:
            raise ValueError("Text2SQL 未生成有效 SQL")
        cleaned = sql.strip().rstrip(";")
        lowered = cleaned.lower()
        if not (lowered.startswith("select") or lowered.startswith("with ")):
            raise ValueError("仅允许执行 SELECT/CTE 查询")
        if _SQL_WRITE_OPERATORS.search(lowered):
            raise ValueError("检测到潜在写操作，已阻断执行")
        if "--" in cleaned or "/*" in cleaned:
            raise ValueError("检测到注释/多语句，已阻断执行")
        if ";" in cleaned:
            raise ValueError("不支持多语句执行")
        if " limit " not in lowered:
            cleaned = f"{cleaned} LIMIT {settings.text2sql_max_rows}"
        return cleaned

    async def train(self, training_data: list[dict]) -> dict:
        """训练：导入Schema和问答对"""
        vn = self._get_vanna()
        for item in training_data:
            vn.train(question=item["question"], sql=item["sql"])
        return {"status": "ok", "count": len(training_data)}
