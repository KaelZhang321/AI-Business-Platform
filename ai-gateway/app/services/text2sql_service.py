from __future__ import annotations

import asyncio
import json
import logging
import re
from pathlib import Path

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

    async def train_from_schema(self, sql_file: str | None = None) -> dict:
        """从 init-postgres.sql 自动导入表结构到 Vanna 训练

        解析 SQL 文件中的 CREATE TABLE 语句，逐条调用 vn.train(ddl=...)。
        """
        logger = logging.getLogger(__name__)
        if sql_file is None:
            sql_file = str(Path(__file__).resolve().parents[3] / "docker" / "init-scripts" / "init-postgres.sql")

        path = Path(sql_file)
        if not path.exists():
            raise FileNotFoundError(f"Schema 文件不存在: {sql_file}")

        content = path.read_text(encoding="utf-8")

        # 提取 CREATE TABLE ... ); 语句块
        ddl_pattern = re.compile(
            r"(CREATE\s+TABLE\s+\w+\s*\(.*?\);)",
            re.IGNORECASE | re.DOTALL,
        )
        ddl_statements = ddl_pattern.findall(content)

        if not ddl_statements:
            return {"status": "ok", "count": 0, "message": "未找到 CREATE TABLE 语句"}

        vn = self._get_vanna()
        trained = 0
        for ddl in ddl_statements:
            try:
                vn.train(ddl=ddl)
                trained += 1
            except Exception as exc:
                logger.warning("训练 DDL 失败: %s — %s", ddl[:60], exc)

        logger.info("Schema 训练完成: %d/%d 条 DDL", trained, len(ddl_statements))
        return {"status": "ok", "count": trained, "total": len(ddl_statements)}
