"""ChatWorkflow 单元测试 — 覆盖 classify→{knowledge,query,task,chat} 四条路径。"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.schemas import (
    ChatRequest,
    IntentResult,
    IntentType,
    SubIntentType,
)
from app.services.chat_workflow import ChatWorkflow


@pytest.fixture()
def mock_services():
    """构建全 mock 的 ChatWorkflow 实例。"""
    return {
        "intent_classifier": MagicMock(),
        "rag_service": MagicMock(),
        "text2sql_service": MagicMock(),
        "dynamic_ui": MagicMock(),
        "llm_service": MagicMock(),
        "semantic_cache": MagicMock(),
    }


def _make_request(message="你好", user_id="u1", stream=False, **kwargs):
    return ChatRequest(message=message, user_id=user_id, stream=stream, **kwargs)


class TestClassifyRoute:
    """意图分类和路由测试。"""

    @pytest.mark.asyncio
    async def test_chat_intent_routes_to_chat_node(self, mock_services):
        """CHAT 意图路由到 _handle_chat。"""
        mock_services["intent_classifier"].classify = AsyncMock(
            return_value=IntentResult(intent=IntentType.CHAT, sub_intent=SubIntentType.GENERAL, confidence=0.9)
        )
        mock_services["llm_service"].chat = AsyncMock(return_value="我是AI助手")

        wf = ChatWorkflow(**mock_services)
        resp = await wf.run(_make_request("你好"))

        assert resp.intent == IntentType.CHAT
        assert resp.content == "我是AI助手"
        mock_services["llm_service"].chat.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_knowledge_intent_routes_to_knowledge_node(self, mock_services):
        """KNOWLEDGE 意图路由到 _handle_knowledge（缓存未命中场景）。"""
        mock_services["intent_classifier"].classify = AsyncMock(
            return_value=IntentResult(
                intent=IntentType.KNOWLEDGE,
                sub_intent=SubIntentType.KNOWLEDGE_POLICY,
                confidence=0.85,
            )
        )
        mock_services["semantic_cache"].lookup = AsyncMock(return_value=None)

        mock_result = MagicMock()
        mock_result.title = "政策文档"
        mock_result.content = "请假需要提前申请" + "x" * 200
        mock_result.model_dump = MagicMock(
            return_value={"title": "政策文档", "content": "请假需要提前申请"}
        )
        mock_services["rag_service"].search = AsyncMock(return_value=[mock_result])
        mock_services["dynamic_ui"].generate_ui_spec = AsyncMock(return_value={"type": "card"})
        mock_services["semantic_cache"].store = AsyncMock()

        wf = ChatWorkflow(**mock_services)
        resp = await wf.run(_make_request("请假政策"))

        assert resp.intent == IntentType.KNOWLEDGE
        assert "政策文档" in resp.content
        mock_services["rag_service"].search.assert_awaited_once()
        mock_services["semantic_cache"].store.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_query_intent_routes_to_query_node(self, mock_services):
        """QUERY 意图路由到 _handle_query。"""
        mock_services["intent_classifier"].classify = AsyncMock(
            return_value=IntentResult(
                intent=IntentType.QUERY,
                sub_intent=SubIntentType.DATA_SALES,
                confidence=0.8,
            )
        )

        mock_t2s_result = MagicMock()
        mock_t2s_result.answer = "上月销售额100万"
        mock_t2s_result.explanation = "SELECT SUM..."
        mock_t2s_result.sql = "SELECT SUM(amount) FROM sales"
        mock_t2s_result.chart_spec = None
        mock_t2s_result.results = [{"total": 1000000}]
        mock_services["text2sql_service"].query = AsyncMock(return_value=mock_t2s_result)
        mock_services["dynamic_ui"].generate_ui_spec = AsyncMock(return_value={"type": "table"})

        wf = ChatWorkflow(**mock_services)
        resp = await wf.run(_make_request("上月销售额"))

        assert resp.intent == IntentType.QUERY
        assert "100万" in resp.content
        mock_services["text2sql_service"].query.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_task_intent_routes_to_task_node(self, mock_services):
        """TASK 意图路由到 _handle_task（business-server 成功响应）。"""
        mock_services["intent_classifier"].classify = AsyncMock(
            return_value=IntentResult(
                intent=IntentType.TASK,
                sub_intent=SubIntentType.TASK_QUERY,
                confidence=0.9,
            )
        )
        mock_services["dynamic_ui"].generate_ui_spec = AsyncMock(return_value={"type": "list"})

        wf = ChatWorkflow(**mock_services)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": {
                "records": [
                    {"title": "审批报销单", "status": "待处理", "sourceSystem": "OA"},
                ]
            }
        }
        wf._http.get = AsyncMock(return_value=mock_resp)

        resp = await wf.run(_make_request("我的待办", user_id="user-1"))

        assert resp.intent == IntentType.TASK
        assert "1 条待办" in resp.content
        assert "审批报销单" in resp.content


class TestKnowledgeCacheHit:
    """语义缓存命中场景。"""

    @pytest.mark.asyncio
    async def test_cache_hit_skips_rag(self, mock_services):
        """语义缓存命中时跳过 RAG 检索。"""
        mock_services["intent_classifier"].classify = AsyncMock(
            return_value=IntentResult(
                intent=IntentType.KNOWLEDGE,
                sub_intent=SubIntentType.GENERAL,
                confidence=0.9,
            )
        )
        cache_result = MagicMock()
        cache_result.similarity = 0.98
        cache_result.answer = "缓存回答"
        cache_result.ui_spec = {"cached": True}
        cache_result.sources = [{"doc_id": "cached"}]
        mock_services["semantic_cache"].lookup = AsyncMock(return_value=cache_result)

        wf = ChatWorkflow(**mock_services)
        resp = await wf.run(_make_request("缓存问题"))

        assert resp.content == "缓存回答"
        mock_services["rag_service"].search.assert_not_called()


class TestSSEFormat:
    """SSE 信封格式测试。"""

    def test_sse_envelope_structure(self):
        """_sse() 生成的信封包含所有必需字段。"""
        result = ChatWorkflow._sse("STREAM_START", {"intent": "chat"}, "trace-123")
        assert result.startswith("event: STREAM_START\n")
        assert "data: " in result

        data_line = result.split("data: ")[1].strip()
        envelope = json.loads(data_line)
        assert envelope["version"] == "1.0"
        assert envelope["traceId"] == "trace-123"
        assert envelope["source"] == "ai-gateway"
        assert envelope["type"] == "STREAM_START"
        assert envelope["payload"] == {"intent": "chat"}
        assert "id" in envelope
        assert "timestamp" in envelope

    @pytest.mark.asyncio
    async def test_stream_yields_flat_strings(self, mock_services):
        """stream() 应该 yield 扁平字符串，不是嵌套 generator。（P0 已修复）"""
        mock_services["intent_classifier"].classify = AsyncMock(
            return_value=IntentResult(
                intent=IntentType.CHAT,
                sub_intent=SubIntentType.GENERAL,
                confidence=0.9,
            )
        )
        mock_services["llm_service"].chat = AsyncMock(return_value="回复")

        wf = ChatWorkflow(**mock_services)
        results = []
        async for item in wf.stream(_make_request("test")):
            results.append(item)

        for item in results:
            assert isinstance(item, str), f"Expected str, got {type(item)}: {item}"
