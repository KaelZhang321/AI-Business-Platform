"""平台通用问数执行器。

该模块负责承接非垂直域的 Text2SQL 请求，重点是把 LLM 生成的 SQL 收敛到只读、
可控、可限流的执行边界内。
"""

from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path

import aiomysql

from app.core.config import reveal_secret, settings
from app.models.schemas import QueryDomain, Text2SQLResponse
from app.services.dynamic_ui_service import DynamicUIService

logger = logging.getLogger(__name__)

_SQL_WRITE_OPERATORS = re.compile(
    r"\b(insert|update|delete|drop|alter|create|grant|revoke|truncate|call|merge)\b",
    re.IGNORECASE,
)

class GenericQueryExecutor:
    """平台通用问数执行器。

    功能：
        用 Vanna 生成 SQL，再通过网关自有 MySQL 连接池执行只读查询，并交给 UI 生成层
        输出基础可视化。

    Edge Cases:
        - SQL 只允许 `SELECT/CTE`
        - 自动补 `LIMIT`，防止大结果集直接拖垮链路
        - 通用问数执行器必须消费上层注入的业务库 pool，避免在 HTTP 请求期间偷偷建池
    """

    def __init__(self, *, pool: aiomysql.Pool | None = None) -> None:
        self._vn = None
        self._dynamic_ui = DynamicUIService()
        self._pool = pool

    def _get_vanna(self):
        """懒加载通用 Vanna 客户端。"""
        if self._vn is None:
            from vanna.milvus import Milvus_VectorStore
            from vanna.openai import OpenAI_Chat

            class VannaOpenAI(Milvus_VectorStore, OpenAI_Chat):
                def __init__(self, config=None):
                    Milvus_VectorStore.__init__(self, config=config)
                    OpenAI_Chat.__init__(self, config=config)

            api_key = reveal_secret(settings.text2sql_api_key)
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
        """执行平台通用问数。

        Args:
            question: 用户自然语言问题。
            database: 逻辑数据库名；当前为兼容参数，底层仍走统一数据源。
            conversation_id: 保留的多轮问数字段，通用链路暂不使用。
            context: 预留上下文字段，通用链路暂不使用。

        Returns:
            标准 `Text2SQLResponse`，其中 `chart_spec` 为规则生成的轻量图表。
        """
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
        """批量训练问答对，提升自然语言到 SQL 的映射准确率。"""
        vn = self._get_vanna()
        for item in training_data:
            await asyncio.to_thread(vn.train, question=item["question"], sql=item["sql"])
        return {"status": "ok", "count": len(training_data)}

    async def train_from_schema(self, sql_file: str | None = None) -> dict[str, int | str]:
        """从 DDL 文件抽取表结构并训练模型。

        功能：
            让 Vanna 在缺少问答样本时，至少先具备数据库结构感知，避免生成完全无关的 SQL。
        """
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
        """执行器不持有连接池所有权，因此 close 为 no-op。"""

    async def _get_pool(self) -> aiomysql.Pool:
        """读取应用级注入的通用问数连接池。"""
        if self._pool is None:
            raise RuntimeError("业务库连接池未注入，请通过 AppResources 或测试桩显式提供。")
        return self._pool

    async def _execute_sql(self, sql: str, database: str) -> list[dict]:
        """在统一数据源上执行只读 SQL。"""
        del database  # 当前 generic executor 仍使用统一数据源
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await asyncio.wait_for(cursor.execute(sql), timeout=settings.text2sql_timeout_seconds)
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    @staticmethod
    def _sanitize_sql(sql: str, max_rows: int) -> str:
        """将模型生成 SQL 收敛到安全只读子集。

        功能：
            这是通用问数最重要的安全闸门，宁可保守拒绝，也不能让写语句、注释逃逸、
            多语句执行或无上限扫描进入数据库。
        """
        if not sql:
            raise ValueError("Text2SQL 未生成有效 SQL")
        cleaned = sql.strip().rstrip(";")
        lowered = cleaned.lower()
        if not (lowered.startswith("select") or lowered.startswith("with ")):
            raise ValueError("仅允许执行 SELECT/CTE 查询")
        if _SQL_WRITE_OPERATORS.search(lowered):
            raise ValueError("检测到潜在写操作，已阻断执行")
        # 注释通常意味着模型返回了多语句或解释性文本，直接阻断比猜测更安全。
        if "--" in cleaned or "/*" in cleaned:
            raise ValueError("检测到注释/多语句，已阻断执行")
        if ";" in cleaned:
            raise ValueError("不支持多语句执行")
        # 自动补 LIMIT 是为了把“模型忘了限流”收敛成固定运行时成本。
        if " limit " not in lowered:
            cleaned = f"{cleaned} LIMIT {max_rows}"
        return cleaned
