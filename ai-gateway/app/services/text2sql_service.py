from __future__ import annotations

from app.core.config import settings
from app.models.schemas import QueryDomain, SubIntentType, Text2SQLResponse
from app.services.generic_query_executor import GenericQueryExecutor

class Text2SQLService:
    """统一问数门面，根据 domain / sub_intent 选择具体执行器。"""

    def __init__(self) -> None:
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
        resolved_domain = self.resolve_domain(domain=domain, sub_intent=sub_intent)
        if resolved_domain is QueryDomain.MEETING_BI:
            if not settings.meeting_bi_enabled:
                raise ValueError("Meeting BI 查询未启用，请先配置 meeting_bi_enabled 和相关连接信息")
            executor = self._get_meeting_bi_executor()
            return await executor.query(question, conversation_id=conversation_id, context=context)

        executor = self._get_generic_executor()
        return await executor.query(question, database=database, conversation_id=conversation_id, context=context)

    async def train(self, training_data: list[dict]) -> dict[str, int | str]:
        return await self._get_generic_executor().train(training_data)

    async def train_from_schema(self, sql_file: str | None = None) -> dict[str, int | str]:
        return await self._get_generic_executor().train_from_schema(sql_file)

    async def close(self) -> None:
        await self._get_generic_executor().close()

    @staticmethod
    def resolve_domain(
        *,
        domain: QueryDomain | str | None = None,
        sub_intent: SubIntentType | str | None = None,
    ) -> QueryDomain:
        if domain:
            return domain if isinstance(domain, QueryDomain) else QueryDomain(str(domain))
        if sub_intent:
            if isinstance(sub_intent, SubIntentType) and sub_intent is SubIntentType.DATA_MEETING_BI:
                return QueryDomain.MEETING_BI
            if str(sub_intent) == SubIntentType.DATA_MEETING_BI.value:
                return QueryDomain.MEETING_BI
        return QueryDomain.GENERIC

    def _get_generic_executor(self) -> GenericQueryExecutor:
        if self._generic_executor is None:
            self._generic_executor = GenericQueryExecutor()
        return self._generic_executor

    def _get_meeting_bi_executor(self):
        if self._meeting_bi_executor is None:
            from app.bi.meeting_bi.ai.query_executor import MeetingBIQueryExecutor

            self._meeting_bi_executor = MeetingBIQueryExecutor()
        return self._meeting_bi_executor
