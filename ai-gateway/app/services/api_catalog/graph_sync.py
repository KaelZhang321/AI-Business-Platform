"""GraphRAG 图同步服务。

功能：
    把 `ApiCatalogEntry + NormalizedFieldBinding` 同步到 Neo4j，并在事务成功提交后触发
    Redis Graph Cache 的定向失效。它的职责不是自己实现图数据库细节，而是把“事务写图”
    和“提交后副作用”清晰切开，避免缓存删除跑到事务前面。
"""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from uuid import uuid4

from app.services.api_catalog.graph_cache import GraphCacheService
from app.services.api_catalog.graph_models import (
    GraphCacheInvalidationRequest,
    GraphSyncImpactResult,
    NormalizedFieldBinding,
)
from app.services.api_catalog.graph_repository import GraphRepository, Neo4jGraphRepository
from app.services.api_catalog.schema import ApiCatalogEntry

GraphSyncCallback = Callable[[GraphSyncImpactResult], Awaitable[None] | None]


class ApiCatalogGraphSyncService:
    """GraphRAG 图同步门面。

    功能：
        把单 API 子图替换抽象成稳定服务接口，统一完成：

        1. 生成本轮 `sync_run_id`
        2. 调用图仓储执行事务原子替换
        3. 在事务成功提交后按 `impacted_api_ids` 定向删除缓存
        4. 向上游暴露同步影响面，供 indexer hook 或后续观测链路消费

    Args:
        graph_repository: 图仓储实现。默认使用 Neo4j 版本。
        graph_cache: Redis Graph Cache 服务。默认使用进程级默认配置。
        post_commit_hook: 可选的提交后回调。只会在图事务与缓存失效都成功完成后触发。
        sync_run_id_factory: 自定义 run id 生成器，主要用于测试和离线任务可追踪性。
    """

    def __init__(
        self,
        *,
        graph_repository: GraphRepository | None = None,
        graph_cache: GraphCacheService | None = None,
        post_commit_hook: GraphSyncCallback | None = None,
        sync_run_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._graph_repository = graph_repository or Neo4jGraphRepository()
        self._graph_cache = graph_cache or GraphCacheService()
        self._post_commit_hook = post_commit_hook
        self._sync_run_id_factory = sync_run_id_factory or (lambda: uuid4().hex)

    async def sync_entry(
        self,
        entry: ApiCatalogEntry,
        bindings: list[NormalizedFieldBinding],
        *,
        metadata_version: str | None = None,
    ) -> GraphSyncImpactResult:
        """同步单个接口的图事实。

        Args:
            entry: 当前需要写入图层的接口目录记录。
            bindings: 该接口请求/响应侧已经完成归一的字段绑定事实。
            metadata_version: 可选的元数据版本号，用于回放一次同步来自哪版治理快照。

        Returns:
            图事务提交后的影响面摘要，至少包含 `api_id`、`impacted_api_ids` 和 `sync_run_id`。

        Raises:
            透传底层图仓储异常。调用方应把这类失败视为“该接口本轮索引失败”，而不是吞掉继续。
        """

        sync_result = await self._graph_repository.sync_api_subgraph(
            entry=entry,
            bindings=bindings,
            sync_run_id=self._sync_run_id_factory(),
            metadata_version=metadata_version,
        )

        # 缓存失效只能发生在图事务提交之后，否则一旦事务回滚，在线链路会在“旧缓存已删、半图未提交”
        # 的时间窗里直接打到空或错误图事实。
        await self._graph_cache.invalidate(
            GraphCacheInvalidationRequest(impacted_api_ids=sync_result.impacted_api_ids)
        )
        await self._run_post_commit_hook(sync_result)
        return sync_result

    async def close(self) -> None:
        """释放服务持有的外部连接。"""

        await self._graph_repository.close()
        await self._graph_cache.close()

    async def _run_post_commit_hook(self, sync_result: GraphSyncImpactResult) -> None:
        """执行提交后回调。

        功能：
            这里允许 indexer 或后续事件桥把 `impacted_api_ids` 接出去，但它们都只能观察已提交事实，
            不能反向参与图事务本身，否则又会把边界重新搅混。
        """

        if self._post_commit_hook is None:
            return

        maybe_awaitable = self._post_commit_hook(sync_result)
        if inspect.isawaitable(maybe_awaitable):
            await maybe_awaitable
