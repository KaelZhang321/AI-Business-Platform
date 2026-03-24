from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import aiomysql

from app.core.config import settings
from app.models.schemas import Text2SQLResponse
from app.services.dynamic_ui_service import DynamicUIService

_SQL_WRITE_OPERATORS = re.compile(
    r"\b(insert|update|delete|drop|alter|create|grant|revoke|truncate|call|merge)\b",
    re.IGNORECASE,
)


def _parse_mysql_url(url: str) -> dict:
    """从 SQLAlchemy 风格 URL 解析 MySQL 连接参数。"""
    # mysql+aiomysql://user:pass@host:port/db?charset=utf8mb4
    cleaned = re.sub(r"^mysql\+\w+://", "mysql://", url)
    parsed = urlparse(cleaned)
    params = parse_qs(parsed.query)
    return {
        "host": parsed.hostname or "localhost",
        "port": parsed.port or 3306,
        "user": parsed.username or "root",
        "password": parsed.password or "",
        "db": (parsed.path or "/").lstrip("/") or "ai_platform",
        "charset": params.get("charset", ["utf8mb4"])[0],
    }


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
        self._pool: aiomysql.Pool | None = None

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
        sql = await asyncio.to_thread(vn.ask, question)
        sanitized_sql = self._sanitize_sql(sql)
        rows = await self._execute_sql(sanitized_sql, database)
        ui_spec = await self._dynamic_ui.generate_ui_spec("query", rows, {"question": question})
        return Text2SQLResponse(
            sql=sanitized_sql,
            explanation=f'自然语言问题 "{question}" 转为 SQL 并执行',
            results=rows,
            chart_spec=ui_spec,
        )

    async def _get_pool(self) -> aiomysql.Pool:
        if self._pool is None:
            conn_params = _parse_mysql_url(settings.database_url)
            self._pool = await aiomysql.create_pool(
                minsize=1,
                maxsize=5,
                **conn_params,
            )
        return self._pool

    async def _execute_sql(self, sql: str, database: str) -> list[dict]:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await asyncio.wait_for(
                    cursor.execute(sql),
                    timeout=settings.text2sql_timeout_seconds,
                )
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

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
            await asyncio.to_thread(vn.train, question=item["question"], sql=item["sql"])
        return {"status": "ok", "count": len(training_data)}

    async def train_from_schema(self, sql_file: str | None = None) -> dict:
        """从 init-mysql.sql 自动导入表结构到 Vanna 训练

        解析 SQL 文件中的 CREATE TABLE 语句，逐条调用 vn.train(ddl=...)。
        """
        logger = logging.getLogger(__name__)
        if sql_file is None:
            sql_file = str(Path(__file__).resolve().parents[3] / "docker" / "init-scripts" / "init-mysql.sql")

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
                await asyncio.to_thread(vn.train, ddl=ddl)
                trained += 1
            except Exception as exc:
                logger.warning("训练 DDL 失败: %s — %s", ddl[:60], exc)

        logger.info("Schema 训练完成: %d/%d 条 DDL", trained, len(ddl_statements))
        return {"status": "ok", "count": trained, "total": len(ddl_statements)}
