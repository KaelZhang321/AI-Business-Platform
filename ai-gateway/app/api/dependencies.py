"""API 路由层统一依赖提供器。

功能：
    把 HTTP 入口需要的应用级共享资源统一收口到 `Depends(...)` 函数，避免每个路由文件
    自己判断 `app.state`、自己维护 fallback 单例。
"""

from __future__ import annotations

from fastapi import Depends, Request

from app.core.resources import AppResources, get_app_resources
from app.services.api_catalog.governance_job_service import ApiCatalogGovernanceJobService
from app.services.api_catalog.registry_source import ApiCatalogRegistrySource
from app.services.api_catalog.semantic_curation_run_repository import SemanticCurationRunRepository
from app.services.api_catalog.semantic_governance_publication_service import SemanticGovernancePublicationService
from app.services.health_quadrant_service import HealthQuadrantService
from app.services.text2sql_service import Text2SQLService
from app.services.transcript_extract_service import TranscriptExtractService
from app.services.ui_catalog_service import UICatalogService


def get_app_resource_container(request: Request) -> AppResources:
    """读取已启动的应用级资源容器。

    功能：
        HTTP 路由只消费 `lifespan` 已经创建好的共享对象，不在请求期间再判断是否需要临时
        创建替代实例。若测试环境没有注入该容器，应通过 `dependency_overrides` 提供桩对象。
    """

    return get_app_resources(request.app)


def get_text2sql_service(resources: AppResources = Depends(get_app_resource_container)) -> Text2SQLService:
    """返回共享 Text2SQL 服务。"""

    return resources.text2sql_service


def get_transcript_extract_service(
    resources: AppResources = Depends(get_app_resource_container),
) -> TranscriptExtractService:
    """返回共享 transcript 抽取服务。"""

    return resources.transcript_extract_service


def get_health_quadrant_service(
    resources: AppResources = Depends(get_app_resource_container),
) -> HealthQuadrantService:
    """返回共享健康四象限服务。"""

    return resources.health_quadrant_service


def get_ui_catalog_service(resources: AppResources = Depends(get_app_resource_container)) -> UICatalogService:
    """返回共享 UI 目录服务。"""

    return resources.ui_catalog_service


def get_api_catalog_registry_source(
    resources: AppResources = Depends(get_app_resource_container),
) -> ApiCatalogRegistrySource:
    """返回共享 API Catalog 注册表访问器。"""

    return resources.api_catalog_registry_source


def get_governance_job_service(
    resources: AppResources = Depends(get_app_resource_container),
) -> ApiCatalogGovernanceJobService:
    """返回共享治理任务服务。"""

    return resources.api_catalog_governance_job_service


def get_curation_run_repository(
    resources: AppResources = Depends(get_app_resource_container),
) -> SemanticCurationRunRepository:
    """返回共享治理 run 仓储。"""

    return resources.semantic_curation_run_repository


def get_publication_service(
    resources: AppResources = Depends(get_app_resource_container),
) -> SemanticGovernancePublicationService:
    """返回共享治理发布服务。"""

    return resources.semantic_governance_publication_service
