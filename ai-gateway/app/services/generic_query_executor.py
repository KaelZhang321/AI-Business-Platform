from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path

import aiomysql

from app.core.config import settings
from app.models.schemas import QueryDomain, Text2SQLResponse
from app.services.dynamic_ui_service import DynamicUIService

logger = logging.getLogger(__name__)

_SQL_WRITE_OPERATORS = re.compile(
    r"\b(insert|update|delete|drop|alter|create|grant|revoke|truncate|call|merge)\b",
    re.IGNORECASE,
)


def _parse_mysql_url() -> dict[str, str | int]:
    """直接从 AI_MYSQL_* 配置生成 aiomysql 连接参数。"""
    return {
        "host": settings.ai_mysql_host,
        "port": settings.ai_mysql_port,
        "user": settings.ai_mysql_user,
        "password": settings.ai_mysql_password,
        "db": settings.ai_mysql_database,
        "charset": "utf8mb4",
    }


class GenericQueryExecutor:
    """平台通用问数执行器。"""

    def __init__(self) -> None:
        self._vn = None
        self._dynamic_ui = DynamicUIService()
        self._pool: aiomysql.Pool | None = None

    def _get_vanna(self):
        if self._vn is None:
            from vanna.milvus import Milvus_VectorStore
            from vanna.openai import OpenAI_Chat

            class VannaOpenAI(Milvus_VectorStore, OpenAI_Chat):
                def __init__(self, config=None):
                    Milvus_VectorStore.__init__(self, config=config)
                    OpenAI_Chat.__init__(self, config=config)

            api_key = settings.text2sql_api_key
            if not api_key:
                raise RuntimeError("Text2SQL 未配置 API Key，请设置 TEXT2SQL_API_KEY 或 ARK_API_KEY")

            self._vn = VannaOpenAI(
                config={
                    "api_key": api_key,
                    "model": settings.text2sql_model,
                    "base_url": settings.text2sql_base_url,
                }
            )
        return self._vn

    async def query(
        self,
        question: str,
        *,
        database: str = "default",
        conversation_id: str | None = None,
        context: dict | None = None,
    ) -> Text2SQLResponse:
        del conversation_id, context  # generic executor 暂不使用多轮上下文
        vn = self._get_vanna()
        sql = await asyncio.to_thread(vn.ask, question)
        sanitized_sql = self._sanitize_sql(sql, settings.text2sql_max_rows)
        rows = await self._execute_sql(sanitized_sql, database)
        ui_spec = await self._dynamic_ui.generate_ui_spec("query", rows, {"question": question})
        return Text2SQLResponse(
            sql=sanitized_sql,
            explanation=f'自然语言问题 "{question}" 转为 SQL 并执行',
            domain=QueryDomain.GENERIC,
            answer=None,
            results=rows,
            chart_spec=ui_spec,
        )

    async def train(self, training_data: list[dict]) -> dict[str, int | str]:
        vn = self._get_vanna()
        for item in training_data:
            await asyncio.to_thread(vn.train, question=item["question"], sql=item["sql"])
        return {"status": "ok", "count": len(training_data)}

    async def train_from_schema(self, sql_file: str | None = None) -> dict[str, int | str]:
        if sql_file is None:
            sql_file = str(Path(__file__).resolve().parents[3] / "docker" / "init-scripts" / "init-mysql.sql")

        path = Path(sql_file)
        if not path.exists():
            raise FileNotFoundError(f"Schema 文件不存在: {sql_file}")

        content = path.read_text(encoding="utf-8")
        ddl_pattern = re.compile(r"(CREATE\s+TABLE\s+\w+\s*\(.*?\);)", re.IGNORECASE | re.DOTALL)
        ddl_statements = ddl_pattern.findall(content)

        if not ddl_statements:
            return {"status": "ok", "count": 0, "message": "未找到 CREATE TABLE 语句"}

        vn = self._get_vanna()
        trained = 0
        for ddl in ddl_statements:
            try:
                await asyncio.to_thread(vn.train, ddl=ddl)
                trained += 1
            except Exception as exc:  # pragma: no cover - runtime safety
                logger.warning("训练 DDL 失败: %s — %s", ddl[:60], exc)

        logger.info("Schema 训练完成: %d/%d 条 DDL", trained, len(ddl_statements))
        return {"status": "ok", "count": trained, "total": len(ddl_statements)}

    async def close(self) -> None:
        if self._pool is not None:
            self._pool.close()
            await self._pool.wait_closed()
            self._pool = None

    async def _get_pool(self) -> aiomysql.Pool:
        if self._pool is None:
            conn_params = _parse_mysql_url()
            self._pool = await aiomysql.create_pool(minsize=1, maxsize=5, **conn_params)
        return self._pool

    async def _execute_sql(self, sql: str, database: str) -> list[dict]:
        del database  # 当前 generic executor 仍使用统一数据源
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await asyncio.wait_for(cursor.execute(sql), timeout=settings.text2sql_timeout_seconds)
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    @staticmethod
    def _sanitize_sql(sql: str, max_rows: int) -> str:
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
            cleaned = f"{cleaned} LIMIT {max_rows}"
        return cleaned
