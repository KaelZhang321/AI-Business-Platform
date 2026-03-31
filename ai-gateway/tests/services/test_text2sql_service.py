from __future__ import annotations

import pytest

from app.core.config import settings
from app.models.schemas import QueryDomain, SubIntentType, Text2SQLResponse
from app.services.text2sql_service import Text2SQLService


class StubGenericExecutor:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def query(
        self,
        question: str,
        *,
        database: str = "default",
        conversation_id: str | None = None,
        context: dict | None = None,
    ) -> Text2SQLResponse:
        self.calls.append(
            {
                "question": question,
                "database": database,
                "conversation_id": conversation_id,
                "context": context,
            }
        )
        return Text2SQLResponse(
            sql="SELECT 1 LIMIT 1",
            explanation="generic query executed",
            domain=QueryDomain.GENERIC,
            results=[{"value": 1}],
        )


class StubMeetingExecutor:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def query(
        self,
        question: str,
        *,
        conversation_id: str | None = None,
        context: dict | None = None,
    ) -> Text2SQLResponse:
        self.calls.append(
            {
                "question": question,
                "conversation_id": conversation_id,
                "context": context,
            }
        )
        return Text2SQLResponse(
            sql="SELECT region, register_count FROM meeting_registration LIMIT 10",
            explanation="meeting bi query executed",
            domain=QueryDomain.MEETING_BI,
            answer="华东区报名人数最高",
            results=[{"region": "华东", "register_count": 12}],
        )


def test_resolve_domain_defaults_to_generic() -> None:
    assert Text2SQLService.resolve_domain() is QueryDomain.GENERIC


def test_resolve_domain_maps_meeting_sub_intent() -> None:
    assert (
        Text2SQLService.resolve_domain(sub_intent=SubIntentType.DATA_MEETING_BI)
        is QueryDomain.MEETING_BI
    )


@pytest.mark.asyncio
async def test_query_uses_generic_executor_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    service = Text2SQLService()
    generic = StubGenericExecutor()
    meeting = StubMeetingExecutor()
    monkeypatch.setattr(service, "_get_generic_executor", lambda: generic)
    monkeypatch.setattr(service, "_get_meeting_bi_executor", lambda: meeting)

    result = await service.query(
        "查询客户总数",
        database="analytics",
        conversation_id="conv-generic",
        context={"source": "chat"},
    )

    assert result.domain is QueryDomain.GENERIC
    assert generic.calls == [
        {
            "question": "查询客户总数",
            "database": "analytics",
            "conversation_id": "conv-generic",
            "context": {"source": "chat"},
        }
    ]
    assert meeting.calls == []


@pytest.mark.asyncio
async def test_query_routes_to_meeting_executor_when_domain_explicit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = Text2SQLService()
    generic = StubGenericExecutor()
    meeting = StubMeetingExecutor()
    monkeypatch.setattr(settings, "meeting_bi_enabled", True)
    monkeypatch.setattr(service, "_get_generic_executor", lambda: generic)
    monkeypatch.setattr(service, "_get_meeting_bi_executor", lambda: meeting)

    result = await service.query(
        "本次会议 ROI 是多少",
        database="ignored",
        domain=QueryDomain.MEETING_BI,
        conversation_id="conv-bi",
        context={"tenant": "beta"},
    )

    assert result.domain is QueryDomain.MEETING_BI
    assert meeting.calls == [
        {
            "question": "本次会议 ROI 是多少",
            "conversation_id": "conv-bi",
            "context": {"tenant": "beta"},
        }
    ]
    assert generic.calls == []


@pytest.mark.asyncio
async def test_query_routes_to_meeting_executor_when_sub_intent_matches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = Text2SQLService()
    generic = StubGenericExecutor()
    meeting = StubMeetingExecutor()
    monkeypatch.setattr(settings, "meeting_bi_enabled", True)
    monkeypatch.setattr(service, "_get_generic_executor", lambda: generic)
    monkeypatch.setattr(service, "_get_meeting_bi_executor", lambda: meeting)

    result = await service.query(
        "统计会议签到人数",
        sub_intent=SubIntentType.DATA_MEETING_BI,
        conversation_id="conv-chat",
    )

    assert result.domain is QueryDomain.MEETING_BI
    assert meeting.calls == [
        {
            "question": "统计会议签到人数",
            "conversation_id": "conv-chat",
            "context": None,
        }
    ]
    assert generic.calls == []


@pytest.mark.asyncio
async def test_query_rejects_meeting_bi_when_feature_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = Text2SQLService()
    monkeypatch.setattr(settings, "meeting_bi_enabled", False)

    with pytest.raises(ValueError, match="Meeting BI 查询未启用"):
        await service.query(
            "查看会议报名人数",
            domain=QueryDomain.MEETING_BI,
        )
