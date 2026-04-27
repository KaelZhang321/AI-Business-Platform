from __future__ import annotations

import asyncio
from dataclasses import dataclass

import aiomysql

from app.core.config import settings
from app.core.mysql import build_business_mysql_conn_params

_SELECT_TEMPLATE_SQL = """
SELECT
    service_code,
    system_prompt,
    user_prompt,
    enabled,
    remark
FROM {table_name}
WHERE service_code = %s
LIMIT 1
""".strip()


@dataclass(frozen=True, slots=True)
class PromptTemplateRecord:
    """Prompt 模板记录。

    功能：
        把数据库行收敛为明确的数据对象，避免服务层继续透传松散 dict，
        让后续模板渲染和错误判断都围绕稳定字段展开。
    """

    service_code: str
    system_prompt: str
    user_prompt: str
    enabled: bool
    remark: str | None = None


class PromptTemplateRepositoryError(RuntimeError):
    """Prompt 模板仓储异常。"""


class PromptTemplateRepository:
    """按 `service_code` 读取 Prompt 模板。

    功能：
        这层故意保持非常薄，只负责模板表读取和连接池生命周期管理，不承担
        `task_code` 映射、Prompt 渲染和模型调用，避免“配置访问”和“业务编排”
        再次混到同一个类里。

    Edge Cases:
        - 当表不存在或 SQL 执行失败时，统一抛出仓储异常，方便上层转成业务错误
        - 同一进程内连接池惰性创建，降低未命中新接口时的额外资源消耗
    """

    def __init__(self, *, table_name: str | None = None) -> None:
        self._table_name = table_name or settings.llm_prompt_template_table
        self._pool: aiomysql.Pool | None = None
        self._pool_lock = asyncio.Lock()

    async def get_by_service_code(self, service_code: str) -> PromptTemplateRecord | None:
        """按服务编码加载单条 Prompt 模板。

        Args:
            service_code: 运行时服务编码。

        Returns:
            命中时返回模板记录，未命中返回 `None`。

        Raises:
            PromptTemplateRepositoryError: 数据库访问失败时抛出。
        """

        normalized_service_code = service_code.strip()
        if not normalized_service_code:
            raise PromptTemplateRepositoryError("service_code 不能为空。")

        sql = _SELECT_TEMPLATE_SQL.format(table_name=self._table_name)
        try:
            pool = await self._get_pool()
            async with pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute(sql, (normalized_service_code,))
                    row = await cursor.fetchone()
        except Exception as exc:  # noqa: BLE001
            raise PromptTemplateRepositoryError(f"读取 Prompt 模板失败: {exc}") from exc

        if not row:
            return None

        return PromptTemplateRecord(
            service_code=str(row.get("service_code") or "").strip(),
            system_prompt=str(row.get("system_prompt") or ""),
            user_prompt=str(row.get("user_prompt") or ""),
            enabled=bool(int(row.get("enabled") or 0)),
            remark=str(row.get("remark") or "").strip() or None,
        )

    async def close(self) -> None:
        """关闭内部连接池。

        功能：
            与项目中其他 MySQL 仓储保持一致，允许应用关闭钩子和测试用例显式释放资源，
            避免热重载后留下悬挂连接。
        """

        if self._pool is not None:
            self._pool.close()
            await self._pool.wait_closed()
            self._pool = None

    async def _get_pool(self) -> aiomysql.Pool:
        """惰性创建 Prompt 模板连接池。"""

        if self._pool is not None:
            return self._pool

        async with self._pool_lock:
            if self._pool is not None:
                return self._pool
            self._pool = await aiomysql.create_pool(
                minsize=1,
                maxsize=3,
                **build_business_mysql_conn_params(),
            )
        return self._pool
