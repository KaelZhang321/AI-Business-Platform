"""统一问数门面。

该模块的职责不是执行 SQL 细节，而是把“平台通用问数”和“会议 BI 专属问数”
收敛到一个稳定入口，确保上游调用方不需要理解具体执行器的差异。
"""

from __future__ import annotations

import aiomysql

from app.core.config import settings
from app.models.schemas.common import SubIntentType
from app.models.schemas.text2sql import (
    QueryDomain,
    Text2SQLResponse,
)
from app.services.generic_query_executor import GenericQueryExecutor


class Text2SQLService:
    """统一问数门面，根据业务域路由到具体执行器。

    功能：
        兼容老的通用问数调用方式，同时为会议 BI 这样的垂直执行器预留明确分流点。

    Edge Cases:
        - 显式传入 `domain` 时优先级高于 `sub_intent`
        - 会议 BI 未启用时，直接阻断并返回清晰配置错误
    """

    def __init__(self, *, generic_pool: aiomysql.Pool | None = None) -> None:
        self._generic_pool = generic_pool
        self._generic_executor: GenericQueryExecutor | None = None
        self._meeting_bi_executor = None

    async def query(
        self,
        question: str,
        *,
        database: str = "default",
        domain: QueryDomain | str | None = None,
        sub_intent: SubIntentType | str | None = None,
        conversation_id: str | None = None,
        context: dict | None = None,
    ) -> Text2SQLResponse:
        """根据业务域执行问数查询。

        Args:
            question: 用户自然语言问题。
            database: 通用问数使用的逻辑数据库名，当前仅保留兼容入口。
            domain: 显式业务域，优先级最高。
            sub_intent: 由上游意图识别出的二级问数域。
            conversation_id: 多轮会话 ID，供垂直执行器做上下文改写。
            context: 额外请求上下文，供垂直执行器使用。

        Returns:
            标准 `Text2SQLResponse`，保证上游路由层只面向统一响应模型。
        """
        resolved_domain = self.resolve_domain(domain=domain, sub_intent=sub_intent)
        if resolved_domain is QueryDomain.MEETING_BI:
            if not settings.meeting_bi_enabled:
                raise ValueError("Meeting BI 查询未启用，请先配置 meeting_bi_enabled 和相关连接信息")
            executor = self._get_meeting_bi_executor()
            return await executor.query(question, conversation_id=conversation_id, context=context)

        executor = self._get_generic_executor()
        return await executor.query(question, database=database, conversation_id=conversation_id, context=context)

    async def train(self, training_data: list[dict]) -> dict[str, int | str]:
        """将问答对写入通用问数训练集。"""
        return await self._get_generic_executor().train(training_data)

    async def train_from_schema(self, sql_file: str | None = None) -> dict[str, int | str]:
        """从初始化 SQL 中提取 DDL，训练通用问数的表结构认知。"""
        return await self._get_generic_executor().train_from_schema(sql_file)

    async def close(self) -> None:
        """关闭已初始化的通用执行器。

        功能：
            shutdown 阶段只释放真实创建过的资源，避免为了关闭而反向实例化执行器。
        """

        if self._generic_executor is not None:
            await self._generic_executor.close()
            self._generic_executor = None

    @staticmethod
    def resolve_domain(
        *,
        domain: QueryDomain | str | None = None,
        sub_intent: SubIntentType | str | None = None,
    ) -> QueryDomain:
        """将显式 domain / 二级意图折叠成统一业务域。

        功能：
            把上游多种路由来源统一成 `QueryDomain`，避免每个调用方重复写相同分流规则。
        """
        if domain:
            return domain if isinstance(domain, QueryDomain) else QueryDomain(str(domain))
        if sub_intent:
            if isinstance(sub_intent, SubIntentType) and sub_intent is SubIntentType.DATA_MEETING_BI:
                return QueryDomain.MEETING_BI
            if str(sub_intent) == SubIntentType.DATA_MEETING_BI.value:
                return QueryDomain.MEETING_BI
        return QueryDomain.GENERIC

    def _get_generic_executor(self) -> GenericQueryExecutor:
        """懒加载通用问数执行器，避免应用启动即初始化重资源对象。"""
        if self._generic_executor is None:
            self._generic_executor = GenericQueryExecutor(pool=self._generic_pool)
        return self._generic_executor

    def _get_meeting_bi_executor(self):
        """懒加载会议 BI 执行器，隔离垂直域依赖。"""
        if self._meeting_bi_executor is None:
            from app.bi.meeting_bi.ai.query_executor import MeetingBIQueryExecutor

            if self._generic_pool is None:
                raise RuntimeError("业务库连接池未注入，无法创建 Meeting BI 执行器。")
            self._meeting_bi_executor = MeetingBIQueryExecutor(pool=self._generic_pool)
        return self._meeting_bi_executor
