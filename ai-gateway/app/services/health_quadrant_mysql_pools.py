"""健康四象限多数据源 MySQL 连接池管理。

功能：
    把 ODS、业务库两套连接池的生命周期统一收敛，避免在请求链路里反复创建和销毁连接池。
    该模块服务于“高并发下连接复用”的稳定性目标。
"""

from __future__ import annotations

import asyncio
import logging

import aiomysql

from app.core.mysql import (
    build_business_mysql_conn_params,
    build_health_quadrant_ods_mysql_conn_params,
)

logger = logging.getLogger(__name__)


class HealthQuadrantMySQLPools:
    """健康四象限多数据源连接池管理器。

    功能：
        统一维护 ODS / BUSINESS 两类连接池，并提供按需懒加载与统一关闭能力。
        该设计的核心目的不是“封装语法”，而是避免请求级连接池抖动导致的吞吐退化。

    Args:
        minsize: 连接池最小连接数。
        maxsize: 连接池最大连接数。
        business_pool: 可选的应用级业务库共享连接池；传入后本管理器只借用，不负责关闭。

    Edge Cases:
        1. 并发首次请求同时触发建池时，通过异步锁确保只建一次。
        2. 某个数据源建池失败不会污染其它数据源连接状态。
        3. 业务库 pool 由 AppResources 注入时，close() 只释放 ODS 自有池，避免双重关闭。
    """

    def __init__(
        self,
        *,
        minsize: int = 1,
        maxsize: int = 3,
        business_pool: aiomysql.Pool | None = None,
    ) -> None:
        self._minsize = minsize
        self._maxsize = maxsize
        self._ods_pool: aiomysql.Pool | None = None
        self._business_pool: aiomysql.Pool | None = business_pool
        self._owns_ods_pool = True
        self._owns_business_pool = business_pool is None
        self._lock = asyncio.Lock()

    async def warmup(self) -> None:
        """预热连接池。

        功能：
            在服务启动阶段主动建立连接池，把首次请求的连接建链耗时前置，降低首包延迟。
            预热是性能优化，不是功能前置条件，因此失败时由上层决定是否降级继续启动。
        """

        await self.get_ods_pool()
        await self.get_business_pool()

    async def get_ods_pool(self) -> aiomysql.Pool:
        """获取 ODS 连接池。"""

        return await self._get_or_create_pool(
            pool_name="ods",
            current_pool=self._ods_pool,
            conn_params=build_health_quadrant_ods_mysql_conn_params(),
        )

    async def get_business_pool(self) -> aiomysql.Pool:
        """获取业务库连接池。"""

        return await self._get_or_create_pool(
            pool_name="business",
            current_pool=self._business_pool,
            conn_params=build_business_mysql_conn_params(),
        )

    async def _get_or_create_pool(
        self,
        *,
        pool_name: str,
        current_pool: aiomysql.Pool | None,
        conn_params: dict[str, str | int | float],
    ) -> aiomysql.Pool:
        """按名称获取或创建连接池。

        功能：
            同一个进程内，连接池应该只有一个实例。该方法通过“双重检查 + 异步锁”
            避免并发首建时重复建池。

        Args:
            pool_name: 连接池名称（`ods` / `business`）。
            current_pool: 当前缓存池实例。
            conn_params: 建池连接参数。

        Returns:
            可用的 `aiomysql.Pool` 实例。

        Raises:
            Exception: 底层建池失败时透传异常给调用方决策降级。
        """

        if current_pool is not None:
            return current_pool

        async with self._lock:
            refreshed_pool = self._get_pool_by_name(pool_name)
            if refreshed_pool is not None:
                return refreshed_pool

            pool = await aiomysql.create_pool(
                minsize=self._minsize,
                maxsize=self._maxsize,
                **conn_params,
            )
            self._set_pool_by_name(pool_name, pool)
            logger.info("health quadrant mysql pool initialized pool=%s", pool_name)
            return pool

    async def close(self) -> None:
        """关闭并释放所有连接池。

        功能：
            在应用 shutdown 阶段统一释放资源，避免进程退出前仍有未关闭连接占用后端资源。
        """

        async with self._lock:
            pools = {
                "ods": (self._ods_pool, self._owns_ods_pool),
                "business": (self._business_pool, self._owns_business_pool),
            }
            self._ods_pool = None
            self._business_pool = None
            self._owns_ods_pool = True
            self._owns_business_pool = True

        for pool_name, (pool, owns_pool) in pools.items():
            if pool is None or not owns_pool:
                continue
            pool.close()
            await pool.wait_closed()
            logger.info("health quadrant mysql pool closed pool=%s", pool_name)

    def _get_pool_by_name(self, pool_name: str) -> aiomysql.Pool | None:
        """按名称读取池实例。"""

        if pool_name == "ods":
            return self._ods_pool
        if pool_name == "business":
            return self._business_pool
        raise ValueError(f"unsupported pool_name: {pool_name}")

    def _set_pool_by_name(self, pool_name: str, pool: aiomysql.Pool) -> None:
        """按名称写入池实例。"""

        if pool_name == "ods":
            self._ods_pool = pool
            self._owns_ods_pool = True
            return
        if pool_name == "business":
            self._business_pool = pool
            self._owns_business_pool = True
            return
        raise ValueError(f"unsupported pool_name: {pool_name}")
