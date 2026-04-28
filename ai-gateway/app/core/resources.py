"""应用级共享资源容器。"""

from __future__ import annotations

import logging

import aiomysql

from app.core.mysql import create_business_mysql_pool
from app.services.api_catalog.business_intents import BusinessIntentCatalogService, set_business_intent_catalog_service
from app.services.api_catalog.governance_job_service import ApiCatalogGovernanceJobService
from app.services.api_catalog.registry_source import ApiCatalogRegistrySource
from app.services.api_catalog.semantic_curation_run_repository import SemanticCurationRunRepository
from app.services.api_catalog.semantic_field_repository import SemanticFieldRepository
from app.services.api_catalog.semantic_governance_proposal_repository import SemanticGovernanceProposalRepository
from app.services.api_catalog.semantic_governance_proposal_service import SemanticGovernanceProposalService
from app.services.api_catalog.ui_blueprint_repository import UiBlueprintRepository
from app.services.api_catalog.semantic_governance_publication_service import SemanticGovernancePublicationService
from app.services.model_runtime_config_service import ModelRuntimeConfigService, set_model_runtime_config_service
from app.services.prompt_template_repository import PromptTemplateRepository
from app.services.rag_service import RAGService
from app.services.health_quadrant_service import HealthQuadrantService
from app.services.text2sql_service import Text2SQLService
from app.services.transcript_extract_service import TranscriptExtractService
from app.services.ui_catalog_service import UICatalogService

logger = logging.getLogger(__name__)


class AppResources:
    """集中管理应用生命周期内的共享外部资源。

    功能：
        将业务 MySQL 连接池从各 repository 的隐式懒加载中收口到应用启动阶段，避免
        在线接口、治理任务和 transcript 抽取各自创建独立连接池，导致连接数不可控。

    Returns:
        启动后提供可直接注入 route/service 的共享服务对象。

    Edge Cases:
        - `start()` 被重复调用时保持幂等，不会重复建池
        - `close()` 会先关闭上层服务缓存，再释放底层共享连接池
    """

    def __init__(self) -> None:
        self.business_mysql_pool: aiomysql.Pool | None = None
        self.rag_service: RAGService | None = None
        self.model_runtime_config_service: ModelRuntimeConfigService | None = None
        self.prompt_template_repository: PromptTemplateRepository | None = None
        self.business_intent_catalog_service: BusinessIntentCatalogService | None = None
        self.ui_catalog_service: UICatalogService | None = None
        self.api_catalog_registry_source: ApiCatalogRegistrySource | None = None
        self.text2sql_service: Text2SQLService | None = None
        self.health_quadrant_service: HealthQuadrantService | None = None
        self.transcript_extract_service: TranscriptExtractService | None = None
        self.semantic_curation_run_repository: SemanticCurationRunRepository | None = None
        self.semantic_field_repository: SemanticFieldRepository | None = None
        self.semantic_governance_proposal_repository: SemanticGovernanceProposalRepository | None = None
        self.semantic_governance_proposal_service: SemanticGovernanceProposalService | None = None
        self.ui_blueprint_repository: UiBlueprintRepository | None = None
        self.semantic_governance_publication_service: SemanticGovernancePublicationService | None = None
        self.api_catalog_governance_job_service: ApiCatalogGovernanceJobService | None = None
        self._started = False

    async def start(self) -> None:
        """创建应用级共享资源。

        Args:
            无业务入参；配置统一读取 `settings.business_mysql_*`。

        Returns:
            `None`。成功后各属性均指向可注入的共享实例。

        Raises:
            Exception: 共享连接池创建失败时向上传递，阻止应用以半初始化状态启动。
        """

        if self._started:
            return

        self.business_mysql_pool = await create_business_mysql_pool(minsize=1, maxsize=10)
        pool = self.business_mysql_pool

        self.rag_service = RAGService()
        self.model_runtime_config_service = ModelRuntimeConfigService(pool=pool)
        set_model_runtime_config_service(self.model_runtime_config_service)
        self.prompt_template_repository = PromptTemplateRepository(pool=pool)
        self.business_intent_catalog_service = BusinessIntentCatalogService(pool=pool)
        set_business_intent_catalog_service(self.business_intent_catalog_service)
        self.ui_catalog_service = UICatalogService(pool=pool)
        self.api_catalog_registry_source = ApiCatalogRegistrySource(pool=pool)
        self.text2sql_service = Text2SQLService(generic_pool=pool)
        self.health_quadrant_service = HealthQuadrantService(business_pool=pool)
        self.transcript_extract_service = TranscriptExtractService(prompt_repository=self.prompt_template_repository)
        self.semantic_curation_run_repository = SemanticCurationRunRepository(pool=pool)
        self.semantic_field_repository = SemanticFieldRepository(pool=pool)
        self.semantic_governance_proposal_repository = SemanticGovernanceProposalRepository(pool=pool)
        self.ui_blueprint_repository = UiBlueprintRepository(pool=pool)
        self.semantic_governance_proposal_service = SemanticGovernanceProposalService(
            ui_blueprint_repository=self.ui_blueprint_repository
        )
        self.semantic_governance_publication_service = SemanticGovernancePublicationService(
            run_repository=self.semantic_curation_run_repository,
            pool=pool,
        )
        self.api_catalog_governance_job_service = ApiCatalogGovernanceJobService(
            registry_source_factory=lambda: self.api_catalog_registry_source or ApiCatalogRegistrySource(pool=pool),
            run_repository=self.semantic_curation_run_repository,
            proposal_service=self.semantic_governance_proposal_service,
            proposal_repository=self.semantic_governance_proposal_repository,
            semantic_field_repository=self.semantic_field_repository,
        )

        self._started = True
        logger.info("AppResources started with shared business MySQL pool")

    async def close(self) -> None:
        """按依赖反向顺序释放应用级资源。

        Returns:
            `None`。资源关闭失败会记录日志并继续处理后续资源，避免单点失败阻断整体退出。

        Edge Cases:
            被注入共享 pool 的 repository 不负责关闭 pool；最终只在本容器关闭一次。
        """

        close_targets = [
            ("api_catalog_governance_job_service", self.api_catalog_governance_job_service),
            ("transcript_extract_service", self.transcript_extract_service),
            ("text2sql_service", self.text2sql_service),
            ("health_quadrant_service", self.health_quadrant_service),
            ("business_intent_catalog_service", self.business_intent_catalog_service),
            ("ui_catalog_service", self.ui_catalog_service),
            ("api_catalog_registry_source", self.api_catalog_registry_source),
            ("semantic_governance_publication_service", self.semantic_governance_publication_service),
            ("semantic_governance_proposal_service", self.semantic_governance_proposal_service),
            ("semantic_governance_proposal_repository", self.semantic_governance_proposal_repository),
            ("ui_blueprint_repository", self.ui_blueprint_repository),
            ("semantic_field_repository", self.semantic_field_repository),
            ("semantic_curation_run_repository", self.semantic_curation_run_repository),
            ("model_runtime_config_service", self.model_runtime_config_service),
            ("prompt_template_repository", self.prompt_template_repository),
            ("rag_service", self.rag_service),
        ]
        for name, target in close_targets:
            close = getattr(target, "close", None)
            if close is None:
                continue
            try:
                await close()
            except Exception as exc:  # noqa: BLE001
                logger.warning("关闭应用资源失败 name=%s error=%s", name, exc)

        if self.business_mysql_pool is not None:
            self.business_mysql_pool.close()
            await self.business_mysql_pool.wait_closed()
            self.business_mysql_pool = None

        set_business_intent_catalog_service(None)
        set_model_runtime_config_service(None)
        self._started = False
        logger.info("AppResources closed")


def get_app_resources(app: object) -> AppResources:
    """从 FastAPI app.state 读取应用资源容器。

    Args:
        app: FastAPI 应用实例；使用 `object` 是为了降低 core 层对 FastAPI 类型的硬依赖。

    Returns:
        已启动的 `AppResources`。

    Raises:
        RuntimeError: 应用生命周期尚未初始化资源容器时抛出。
    """

    resources = getattr(getattr(app, "state", None), "resources", None)
    if not isinstance(resources, AppResources):
        raise RuntimeError("AppResources 尚未初始化")
    return resources
