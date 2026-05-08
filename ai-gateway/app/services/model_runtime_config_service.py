"""运行时模型配置服务（MySQL 驱动）。

功能：
    把“服务编码 -> 模型后端列表”的配置统一收敛到业务库，避免各业务链路继续各自读取
    `.env` 并维护重复路由逻辑。
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import aiomysql

from app.core.config import settings
from app.services.model_router import ModelBackend

_DEFAULT_CHAT_PATH = "v1/chat/completions"
_DEFAULT_TABLE = "llm_service_backend_config"
logger = logging.getLogger(__name__)


class ModelRuntimeConfigServiceError(RuntimeError):
    """运行时模型配置异常。"""


class ModelRuntimeConfigService:
    """运行时模型配置服务。

    功能：
        1. 从 MySQL 读取指定 `service_code` 的后端配置；
        2. 以短 TTL 缓存配置，降低热点请求的数据库压力；
        3. 把数据库记录转换为 `ModelBackend`，供 `ModelRouter` 直接消费。

    Args:
        cache_ttl_seconds: 配置缓存秒数。
        table_name: 配置表名，默认 `llm_service_backend_config`。

    Edge Cases:
        - 未配置任何启用后端时会抛异常，阻止服务静默落回旧逻辑。
        - `chat_path` 若被错误写成绝对路径（`/v1/...`），会自动规范为相对路径。
        - 业务库连接池必须由应用级组合根注入，避免 leaf service 自己决定资源所有权。
    """

    def __init__(
        self,
        *,
        cache_ttl_seconds: int | None = None,
        table_name: str | None = None,
        pool: aiomysql.Pool | None = None,
    ) -> None:
        self._cache_ttl_seconds = cache_ttl_seconds or settings.llm_runtime_config_cache_ttl_seconds
        self._table_name = table_name or settings.llm_runtime_config_table
        self._pool = pool
        self._cache_lock = asyncio.Lock()
        self._cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}

    async def get_backends(self, service_code: str) -> list[ModelBackend]:
        """获取某条业务链路的后端列表。

        Args:
            service_code: 业务服务编码，例如 `api.query`。

        Returns:
            按优先级排序的 `ModelBackend` 列表。

        Raises:
            ModelRuntimeConfigServiceError: 配置缺失或配置非法时抛出。
        """

        normalized_service_code = service_code.strip()
        if not normalized_service_code:
            raise ModelRuntimeConfigServiceError("service_code 不能为空。")

        # 1) 先走进程内 TTL 缓存，降低高并发下的数据库读放大。
        now = time.monotonic()
        cached = self._cache.get(normalized_service_code)
        if cached and cached[0] > now:
            logger.info(
                "model runtime config cache hit service_code=%s ttl_remaining_seconds=%.2f",
                normalized_service_code,
                cached[0] - now,
            )
            return self._rows_to_backends(cached[1], normalized_service_code)

        # 2) 缓存失效后仅允许一个协程回源，避免同一秒内并发击穿数据库。
        async with self._cache_lock:
            second_cached = self._cache.get(normalized_service_code)
            now = time.monotonic()
            if second_cached and second_cached[0] > now:
                logger.info(
                    "model runtime config cache hit after lock service_code=%s ttl_remaining_seconds=%.2f",
                    normalized_service_code,
                    second_cached[0] - now,
                )
                return self._rows_to_backends(second_cached[1], normalized_service_code)

            logger.info(
                "model runtime config cache miss service_code=%s table=%s, loading from db",
                normalized_service_code,
                self._table_name,
            )
            rows = await self._load_rows_from_db(normalized_service_code)
            if not rows:
                raise ModelRuntimeConfigServiceError(
                    f"service_code={normalized_service_code} 未配置启用中的模型后端。"
                )

            expire_at = now + self._cache_ttl_seconds
            self._cache[normalized_service_code] = (expire_at, rows)
            logger.info(
                "model runtime config loaded service_code=%s backend_count=%s cache_ttl_seconds=%s",
                normalized_service_code,
                len(rows),
                self._cache_ttl_seconds,
            )
            return self._rows_to_backends(rows, normalized_service_code)

    async def close(self) -> None:
        """关闭连接池并清理缓存。"""

        self._cache.clear()

    async def _load_rows_from_db(self, service_code: str) -> list[dict[str, Any]]:
        """从数据库读取模型后端配置。"""

        sql = f"""
SELECT
    backend_name,
    backend_type,
    base_url,
    model_name,
    api_key,
    chat_path,
    priority,
    enabled
FROM {self._table_name}
WHERE service_code = %s
  AND enabled = 1
ORDER BY priority ASC, id ASC
""".strip()
        try:
            pool = await self._get_pool()
            async with pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute(sql, (service_code,))
                    rows = await cursor.fetchall()
        except Exception as exc:  # noqa: BLE001
            raise ModelRuntimeConfigServiceError(f"读取模型配置失败: {exc}") from exc
        logger.info(
            "model runtime config db rows fetched service_code=%s row_count=%s rows=%s",
            service_code,
            len(rows),
            [
                {
                    "backend_name": str(row.get("backend_name") or ""),
                    "backend_type": str(row.get("backend_type") or ""),
                    "base_url": str(row.get("base_url") or ""),
                    "chat_path": str(row.get("chat_path") or ""),
                    "model_name": str(row.get("model_name") or ""),
                    "priority": int(row.get("priority") or 0),
                    "enabled": int(row.get("enabled") or 0),
                }
                for row in rows
            ],
        )
        return [dict(row) for row in rows]

    def _rows_to_backends(self, rows: list[dict[str, Any]], service_code: str) -> list[ModelBackend]:
        """将配置行转换为 Router 后端结构。"""

        backends: list[ModelBackend] = []
        for row in rows:
            name = str(row.get("backend_name") or "").strip()
            backend_type = str(row.get("backend_type") or "").strip().lower()
            base_url = str(row.get("base_url") or "").strip()
            model_name = str(row.get("model_name") or "").strip()
            chat_path = self._normalize_chat_path(row.get("chat_path"))

            if not name or not backend_type or not base_url or not model_name:
                raise ModelRuntimeConfigServiceError(
                    f"service_code={service_code} 存在不完整模型配置，请检查 backend_name/backend_type/base_url/model_name。"
                )
            if backend_type not in {"ollama", "openai", "vllm"}:
                raise ModelRuntimeConfigServiceError(
                    f"service_code={service_code} 的 backend_type={backend_type} 非法，仅支持 ollama/openai/vllm。"
                )

            backends.append(
                ModelBackend(
                    name=name,
                    type=backend_type,
                    base_url=base_url,
                    model=model_name,
                    api_key=self._normalize_nullable_text(row.get("api_key")),
                    chat_path=chat_path,
                    priority=int(row.get("priority") or 0),
                    enabled=bool(int(row.get("enabled") or 0)),
                )
            )

        if not backends:
            raise ModelRuntimeConfigServiceError(f"service_code={service_code} 没有可用后端。")
        # 双重排序兜底：即使底层 SQL 被替换或驱动返回顺序异常，也保证路由优先级稳定。
        return sorted(backends, key=lambda backend: backend.priority)

    async def _get_pool(self) -> aiomysql.Pool:
        """读取应用级注入的业务库连接池。

        功能：
            运行时模型配置属于典型的 DB-backed 读服务，资源归属只允许在应用启动期决定。
            这里显式拒绝运行期自建 pool，避免测试和生产路径再次分叉。
        """

        if self._pool is None:
            raise ModelRuntimeConfigServiceError("业务库连接池未注入，请通过 AppResources 或测试依赖显式提供。")
        return self._pool

    @staticmethod
    def _normalize_chat_path(raw_path: Any) -> str:
        """规范化 `chat_path`。"""

        path = str(raw_path or "").strip() or _DEFAULT_CHAT_PATH
        # 使用相对路径是为了兼容 Ark 等带 `/api/v3` 前缀的 OpenAI-compatible 网关。
        return path.lstrip("/")

    @staticmethod
    def _normalize_nullable_text(value: Any) -> str | None:
        """把空字符串统一转为 `None`。"""

        text = str(value or "").strip()
        return text or None


_model_runtime_config_service: ModelRuntimeConfigService | None = None


def get_model_runtime_config_service() -> ModelRuntimeConfigService:
    """获取进程级模型配置服务单例。"""

    global _model_runtime_config_service
    if _model_runtime_config_service is None:
        raise RuntimeError("ModelRuntimeConfigService 尚未初始化，请先完成 AppResources.start()")
    return _model_runtime_config_service


def set_model_runtime_config_service(service: ModelRuntimeConfigService | None) -> None:
    """替换进程级模型配置服务实例。

    功能：
        应用级资源容器会注入共享业务库连接池，历史调用方仍通过全局 getter 获取服务。
        这里提供显式替换入口，避免每条 LLM 链路继续自行创建连接池。
    """

    global _model_runtime_config_service
    _model_runtime_config_service = service


async def close_model_runtime_config_service() -> None:
    """关闭进程级模型配置服务。"""

    global _model_runtime_config_service
    if _model_runtime_config_service is not None:
        await _model_runtime_config_service.close()
        _model_runtime_config_service = None
