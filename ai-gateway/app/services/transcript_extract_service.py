"""Transcript 信息提取服务。"""

from __future__ import annotations

import logging

from app.core.config import settings
from app.core.error_codes import BusinessError, ErrorCode
from app.models.schemas.transcript_extract import TranscriptExtractData
from app.services.model_router import ModelRouter
from app.services.model_runtime_config_service import get_model_runtime_config_service
from app.services.prompt_template_repository import (
    PromptTemplateRecord,
    PromptTemplateRepository,
    PromptTemplateRepositoryError,
)
from app.utils.json_utils import parse_dirty_json_object, summarize_log_text

logger = logging.getLogger(__name__)

# 当前只落 3 个固定任务。先用代码常量冻结映射，避免在业务尚未稳定时再引入一张任务注册表，
# 导致“task_code -> service_code”也变成第二个配置面。
TASK_TO_SERVICE_CODE = {
    "task1": "transcript.extract.task1",
    "task2": "transcript.extract.task2",
    "task3": "transcript.extract.task3",
}


class TranscriptExtractService:
    """统一承接 transcript 抽取链路。

    功能：
        负责把前端传入的 `task_code` 路由到内部 `service_code`，再串联：
        Prompt 模板查询、模型后端查询、Prompt 渲染、LLM 调用与 JSON 结果解析。

    Args:
        prompt_repository: Prompt 模板仓储，默认使用业务库表。

    Returns:
        `TranscriptExtractData`，供 route 层直接包装统一响应壳。

    Edge Cases:
        - `task_code` 不在白名单中时，必须在服务层就拒绝，避免误打到未知模型配置
        - 模型输出不是 JSON object 时显式报错，不能把脏文本伪装成成功结果
        - 模板禁用与模板缺失都视为不可服务，避免前端拿到半配置状态
    """

    def __init__(self, *, prompt_repository: PromptTemplateRepository | None = None) -> None:
        self._prompt_repository = prompt_repository or PromptTemplateRepository()
        self._routers: dict[str, ModelRouter] = {}

    async def extract(self, *, task_code: str, transcript: str) -> TranscriptExtractData:
        """执行一次 transcript 抽取。

        Args:
            task_code: 抽取任务编码。
            transcript: 原始语音转写文本。

        Returns:
            结构化抽取结果对象。

        Raises:
            BusinessError: 当任务不存在、模板缺失、模型不可用或返回非法 JSON 时抛出。
        """

        normalized_task_code = task_code.strip()
        normalized_transcript = transcript.strip()
        if not normalized_task_code:
            raise BusinessError(ErrorCode.BAD_REQUEST, "taskCode 不能为空")
        if not normalized_transcript:
            raise BusinessError(ErrorCode.BAD_REQUEST, "transcript 不能为空")

        service_code = TASK_TO_SERVICE_CODE.get(normalized_task_code)
        if service_code is None:
            raise BusinessError(ErrorCode.BAD_REQUEST, f"unsupported taskCode: {normalized_task_code}")

        template = await self._load_prompt_template(service_code)
        rendered_user_prompt = self._render_user_prompt(template.user_prompt, normalized_transcript)
        messages = [
            {"role": "system", "content": template.system_prompt},
            {"role": "user", "content": rendered_user_prompt},
        ]
        logger.info(
            "transcript extract llm request task_code=%s service_code=%s transcript_length=%s",
            normalized_task_code,
            service_code,
            len(normalized_transcript),
        )
        router = await self._get_router(service_code)
        try:
            raw_content = await router.chat(
                messages,
                temperature=0,
                response_format={"type": "json_object"},
                timeout_seconds=settings.transcript_extract_llm_timeout_seconds,
            )
        except Exception as exc:  # noqa: BLE001
            raise BusinessError(ErrorCode.LLM_CALL_FAILED, f"transcript 抽取失败: {exc}") from exc

        result = parse_dirty_json_object(raw_content)
        if not result:
            logger.warning(
                "transcript extract llm invalid json task_code=%s service_code=%s raw=%s",
                normalized_task_code,
                service_code,
                summarize_log_text(raw_content),
            )
            raise BusinessError(ErrorCode.LLM_CALL_FAILED, "模型未返回合法 JSON 对象")

        return TranscriptExtractData(
            task_code=normalized_task_code,
            service_code=service_code,
            result=result,
        )

    async def close(self) -> None:
        """释放仓储连接池和模型客户端。

        功能：
            transcript 抽取链路会同时持有 DB 连接池和按 `service_code` 缓存的 Router。
            如果不在应用关闭时主动释放，热重载与测试进程会不断累积悬挂连接。
        """

        await self._prompt_repository.close()
        for router in self._routers.values():
            await router.close()
        self._routers.clear()

    async def _load_prompt_template(self, service_code: str) -> PromptTemplateRecord:
        """加载并校验 Prompt 模板。"""

        try:
            template = await self._prompt_repository.get_by_service_code(service_code)
        except PromptTemplateRepositoryError as exc:
            raise BusinessError(ErrorCode.EXTERNAL_SERVICE_ERROR, str(exc)) from exc

        if template is None:
            raise BusinessError(ErrorCode.RESOURCE_NOT_FOUND, f"Prompt 模板不存在: {service_code}")
        if not template.enabled:
            raise BusinessError(ErrorCode.BAD_REQUEST, f"Prompt 模板未启用: {service_code}")
        if not template.system_prompt.strip() or not template.user_prompt.strip():
            raise BusinessError(ErrorCode.BAD_REQUEST, f"Prompt 模板不完整: {service_code}")
        return template

    async def _get_router(self, service_code: str) -> ModelRouter:
        """按服务编码懒加载并缓存 Router。

        功能：
            三个 transcript 任务允许各自绑定不同模型后端。这里按 `service_code` 做缓存，
            避免同一任务高频请求下重复读库和重复初始化 HTTP 客户端。
        """

        router = self._routers.get(service_code)
        if router is not None:
            return router

        backends = await get_model_runtime_config_service().get_backends(service_code)
        router = ModelRouter(backends=backends)
        self._routers[service_code] = router
        return router

    @staticmethod
    def _render_user_prompt(template: str, transcript: str) -> str:
        """渲染用户 Prompt。

        功能：
            第一版只支持 `{{ transcript }}` 一个占位符，原因是当前任务目标明确，
            引入更复杂模板引擎只会扩大治理面。后续变量增多时再演进为通用渲染器。
        """

        return template.replace("{{ transcript }}", transcript)
