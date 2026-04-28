"""POST /api/v1/chat 契约护栏测试。

目标：锁定当前非流式路由的成功/失败边界和响应 schema，
在后续重构时防止 public API 漂移。
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.models.schemas import ChatRequest, ChatResponse, IntentType


@pytest.fixture()
def mock_workflow():
    """Mock ChatWorkflow 避免触发真实 LLM/RAG 调用。"""
    with patch("app.api.routes.chat.workflow") as mock_wf:
        yield mock_wf


@pytest.fixture()
def client(mock_workflow):
    from app.main import app
    return TestClient(app)


class TestNonStreamChat:
    """非流式 /api/v1/chat 成功与失败边界。"""

    def test_success_returns_chat_response_schema(self, client, mock_workflow):
        """成功请求返回 ChatResponse schema。"""
        mock_workflow.run = AsyncMock(return_value=ChatResponse(
            conversation_id="conv-123",
            intent=IntentType.CHAT,
            content="你好！",
            ui_spec=None,
            sources=[],
        ))
        resp = client.post("/api/v1/chat", json={
            "message": "你好",
            "user_id": "user-1",
            "stream": False,
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["conversation_id"] == "conv-123"
        assert body["intent"] == "chat"
        assert body["content"] == "你好！"
        assert "ui_spec" in body
        assert "sources" in body

    def test_knowledge_intent_returns_sources(self, client, mock_workflow):
        """KNOWLEDGE 意图返回 sources 和 ui_spec。"""
        mock_workflow.run = AsyncMock(return_value=ChatResponse(
            conversation_id="conv-456",
            intent=IntentType.KNOWLEDGE,
            content="根据知识库...",
            ui_spec={"type": "card", "data": []},
            sources=[{"doc_id": "d1", "title": "政策文档"}],
        ))
        resp = client.post("/api/v1/chat", json={
            "message": "请假政策是什么",
            "user_id": "user-1",
            "stream": False,
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["intent"] == "knowledge"
        assert len(body["sources"]) == 1
        assert body["ui_spec"] is not None

    def test_missing_message_returns_422(self, client, mock_workflow):
        """缺少必填字段 message 返回 422。"""
        resp = client.post("/api/v1/chat", json={
            "user_id": "user-1",
            "stream": False,
        })
        assert resp.status_code == 422

    def test_missing_user_id_returns_422(self, client, mock_workflow):
        """缺少必填字段 user_id 返回 422。"""
        resp = client.post("/api/v1/chat", json={
            "message": "hello",
            "stream": False,
        })
        assert resp.status_code == 422

    def test_workflow_exception_returns_500(self, client, mock_workflow):
        """workflow.run 抛异常时返回 500。"""
        mock_workflow.run = AsyncMock(side_effect=RuntimeError("LLM unavailable"))
        resp = client.post("/api/v1/chat", json={
            "message": "test",
            "user_id": "user-1",
            "stream": False,
        })
        assert resp.status_code == 500


class TestStreamChat:
    """流式 /api/v1/chat SSE 包结构锁定。"""

    def test_stream_single_stream_end(self, client, mock_workflow):
        """成功流应该只发一次 STREAM_END。（P0 已修复：route 层不再补发）"""
        async def fake_stream(request):
            from app.services.chat_workflow import ChatWorkflow
            yield ChatWorkflow._sse("STREAM_START", {"intent": "chat"}, "trace-1")
            yield ChatWorkflow._sse("STREAM_CHUNK", {"text": "你好"}, "trace-1")
            yield ChatWorkflow._sse("STREAM_END", {"status": "completed"}, "trace-1")

        mock_workflow.stream = fake_stream
        with client.stream("POST", "/api/v1/chat", json={
            "message": "你好",
            "user_id": "user-1",
            "stream": True,
        }) as resp:
            assert resp.status_code == 200
            raw = resp.read().decode()
            events = []
            for segment in raw.split("\n"):
                segment = segment.strip()
                while segment.startswith("data: "):
                    segment = segment[6:]
                if not segment or not segment.startswith("{"):
                    continue
                try:
                    events.append(json.loads(segment))
                except json.JSONDecodeError:
                    continue
            stream_ends = [e for e in events if e.get("type") == "STREAM_END"]
            assert len(stream_ends) == 1, f"Expected 1 STREAM_END, got {len(stream_ends)}"

    def test_stream_sse_envelope_fields(self, client, mock_workflow):
        """SSE 信封必须包含 version/id/traceId/timestamp/source/type/payload 字段。"""
        async def fake_stream(request):
            from app.services.chat_workflow import ChatWorkflow
            yield ChatWorkflow._sse("STREAM_START", {"intent": "chat"}, "trace-1")
            yield ChatWorkflow._sse("STREAM_END", {"status": "completed"}, "trace-1")

        mock_workflow.stream = fake_stream
        with client.stream("POST", "/api/v1/chat", json={
            "message": "test",
            "user_id": "user-1",
            "stream": True,
        }) as resp:
            # EventSourceResponse 会再次包装 yield 内容，
            # 从 raw 响应体中提取所有 JSON 对象进行验证
            # EventSourceResponse 双层包装：yield 的 "data: {json}" 变成 "data: data: {json}"
            raw = resp.read().decode()
            found = False
            for segment in raw.split("\n"):
                segment = segment.strip()
                # 剥离所有 "data: " 前缀层
                while segment.startswith("data: "):
                    segment = segment[6:]
                if not segment or not segment.startswith("{"):
                    continue
                try:
                    envelope = json.loads(segment)
                    if "version" in envelope:
                        assert "id" in envelope
                        assert "traceId" in envelope
                        assert "timestamp" in envelope
                        assert "source" in envelope
                        assert "type" in envelope
                        assert "payload" in envelope
                        found = True
                        break
                except json.JSONDecodeError:
                    continue
            assert found, f"No valid SSE envelope found in response: {raw[:500]}"
