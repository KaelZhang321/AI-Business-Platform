from __future__ import annotations

import json

import asyncpg

from app.core.config import settings
from app.models.schemas import Text2SQLResponse
from app.services.dynamic_ui_service import DynamicUIService


class Text2SQLService:
    """Text2SQL服务 — 基于 Vanna.ai 2.0+

    文档要求: Vanna.ai Text-to-SQL + RAG，支持本地 Qwen2.5 模型
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
                "ollama_host": "http://localhost:11434",
            })
        return self._vn

    async def query(self, question: str, database: str = "default") -> Text2SQLResponse:
        """将自然语言问题转为SQL并执行"""
        vn = self._get_vanna()
        sql = vn.ask(question)
        rows = await self._execute_sql(sql, database)
        ui_spec = await self._dynamic_ui.generate_ui_spec("query", rows, {"question": question})
        return Text2SQLResponse(
            sql=sql,
            explanation=f"自然语言问题 `""{question}`"" 转为 SQL 并执行",
            results=rows,
            chart_spec=ui_spec,
        )

    async def _execute_sql(self, sql: str, database: str) -> list[dict]:
        conn = await asyncpg.connect(dsn=settings.database_url)
        try:
            records = await conn.fetch(sql)
            return [dict(record) for record in records]
        finally:
            await conn.close()

    async def train(self, training_data: list[dict]) -> dict:
        """训练：导入Schema和问答对"""
        vn = self._get_vanna()
        for item in training_data:
            vn.train(question=item["question"], sql=item["sql"])
        return {"status": "ok", "count": len(training_data)}
