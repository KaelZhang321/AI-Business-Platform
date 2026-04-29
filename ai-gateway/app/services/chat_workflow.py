from __future__ import annotations

import json
import logging
import time
from typing import Any, TypedDict
from uuid import uuid4

import httpx
from langgraph.graph import END, StateGraph

from app.core.config import settings
from app.models.schemas.common import (
    IntentResult,
    IntentType,
    SubIntentType,
)
from app.models.schemas.chat import (
    ChatRequest,
    ChatResponse,
)
from app.services.dynamic_ui_service import DynamicUIService
from app.services.intent_classifier import IntentClassifier
from app.services.llm_service import LLMService
from app.services.rag_service import RAGService
from app.services.semantic_cache import SemanticCacheService
from app.services.text2sql_service import Text2SQLService
from app.utils.timing import StageTimer

logger = logging.getLogger(__name__)


class ChatState(TypedDict, total=False):
    """聊天工作流在 LangGraph 中流转的共享状态。"""

    request: dict[str, Any]
    intent: IntentType | None
    sub_intent: SubIntentType | None
    response_text: str
    ui_spec: dict[str, Any] | None
    sources: list[dict[str, Any]]


class ChatWorkflow:
    """聊天总工作流。

    功能：
        统一承接聊天、知识检索、问数、待办等多种入口，把意图分类和能力路由固定在一条
        可观测、可流式输出的状态图中。

    Edge Cases:
        - 上游能力失败时，优先做业务降级而不是直接把底层异常抛给用户
        - 流式模式与非流式模式共享同一状态图，避免两套分叉逻辑长期漂移
    """

    def __init__(
        self,
        *,
        intent_classifier: IntentClassifier | None = None,
        rag_service: RAGService | None = None,
        text2sql_service: Text2SQLService | None = None,
        dynamic_ui: DynamicUIService | None = None,
        llm_service: LLMService | None = None,
        semantic_cache: SemanticCacheService | None = None,
    ) -> None:
        self._intent_classifier = intent_classifier or IntentClassifier()
        self._rag_service = rag_service or RAGService()
        self._text2sql_service = text2sql_service or Text2SQLService()
        self._dynamic_ui = dynamic_ui or DynamicUIService()
        self._llm_service = llm_service or LLMService()
        self._semantic_cache = semantic_cache or SemanticCacheService()
        self._http = httpx.AsyncClient(timeout=15)
        self._graph = self._build_graph()

    async def close(self) -> None:
        """关闭内部 httpx 客户端。"""
        await self._http.aclose()

    def _build_graph(self):
        """构建意图驱动的 LangGraph 状态图。"""
        graph = StateGraph(ChatState)
        graph.add_node("classify", self._classify_intent)
        graph.add_node("knowledge", self._handle_knowledge)
        graph.add_node("query", self._handle_query)
        graph.add_node("task", self._handle_task)
        graph.add_node("chat", self._handle_chat)

        graph.set_entry_point("classify")
        graph.add_conditional_edges(
            "classify",
            self._route_intent,
            {
                IntentType.KNOWLEDGE: "knowledge",
                IntentType.QUERY: "query",
                IntentType.TASK: "task",
                IntentType.CHAT: "chat",
                "default": "chat",
            },
        )
        for node in ("knowledge", "query", "task", "chat"):
            graph.add_edge(node, END)
        return graph.compile()

    async def run(self, request: ChatRequest) -> ChatResponse:
        """执行非流式聊天工作流。"""
        state = await self._graph.ainvoke(self._initial_state(request))
        return self._to_response(request, state)

    async def stream(self, request: ChatRequest):
        """执行流式聊天工作流，并把状态节点事件转换为 SSE 片段。

        修复记录（P0 SSE 正确性）：
        - _convert_event 从 generator 改为返回 list，避免嵌套 generator
        - trace_id 在请求入口生成一次，全流内保持稳定
        - 异常时发出 STREAM_ERROR 而非静默失败
        """
        initial_state = self._initial_state(request)
        # P0 fix: 请求级稳定 traceId，不依赖可能为空的 conversation_id
        trace_id = request.conversation_id or str(uuid4())
        try:
            async for event in self._graph.astream_events(initial_state, version="v1"):
                # P0 fix: _convert_event 返回 list 而非 generator，逐条 yield 扁平字符串
                for sse_chunk in self._convert_event(request, event, trace_id):
                    yield sse_chunk
        except Exception as exc:
            logger.exception("Stream error: %s", exc)
            yield self._sse("STREAM_ERROR", {"error": str(exc)}, trace_id)

    def _convert_event(self, request: ChatRequest, event: dict[str, Any], trace_id: str) -> list[str]:
        """把 LangGraph 内部事件折叠为统一 SSE 信封。

        返回 SSE 字符串列表（而非 generator），由 stream() 逐条 yield。
        """
        event_type: str | None = event.get("event")
        name: str | None = event.get("name")
        state = event.get("data", {}).get("state", {})
        results: list[str] = []

        if event_type == "on_node_end" and name == "classify":
            intent = state.get("intent", IntentType.CHAT)
            sub_intent = state.get("sub_intent", SubIntentType.GENERAL)
            payload = {
                "intent": intent.value if isinstance(intent, IntentType) else intent,
                "sub_intent": sub_intent.value if isinstance(sub_intent, SubIntentType) else sub_intent,
            }
            results.append(self._sse("STREAM_START", payload, trace_id))
        elif event_type == "on_node_end" and name in {"knowledge", "query", "task", "chat"}:
            text = state.get("response_text", "")
            if text:
                results.append(self._sse("STREAM_CHUNK", {"node": name, "text": text}, trace_id))
            if state.get("ui_spec"):
                results.append(self._sse("STREAM_CHUNK", {"ui_spec": state["ui_spec"]}, trace_id))
            if sources := state.get("sources"):
                results.append(self._sse("STREAM_CHUNK", {"sources": sources}, trace_id))
        elif event_type == "on_graph_end":
            final_state = state if state else {}
            response = self._to_response(request, final_state)
            results.append(self._sse("STREAM_END", response.model_dump(), trace_id))

        return results

    def _initial_state(self, request: ChatRequest) -> ChatState:
        """初始化图执行状态。"""
        return {
            "request": request.model_dump(),
            "intent": None,
            "sub_intent": None,
            "response_text": "",
            "ui_spec": None,
            "sources": [],
        }

    async def _classify_intent(self, state: ChatState) -> dict[str, Any]:
        """工作流入口节点：识别一级/二级意图。"""
        req = ChatRequest(**state["request"])
        timer = StageTimer()
        with timer.stage("intent_classify"):
            result: IntentResult = await self._intent_classifier.classify(req.message, req.context)
        timer.log_summary("classify_intent")
        return {"intent": result.intent, "sub_intent": result.sub_intent}

    async def _handle_knowledge(self, state: ChatState) -> dict[str, Any]:
        """知识检索节点。

        功能：
            优先命中语义缓存，其次检索知识库，并在成功时写回缓存，兼顾稳定性与成本。
        """
        req = ChatRequest(**state["request"])
        timer = StageTimer()

        # S5-11: 语义缓存 — 命中则直接返回
        with timer.stage("semantic_cache_lookup"):
            cache_hit = await self._semantic_cache.lookup(req.message)
        if cache_hit:
            logger.info("语义缓存命中 (similarity=%.4f)", cache_hit.similarity)
            timer.log_summary("handle_knowledge")
            return {
                "response_text": cache_hit.answer,
                "ui_spec": cache_hit.ui_spec,
                "sources": cache_hit.sources,
            }

        with timer.stage("rag_search"):
            results = await self._rag_service.search(req.message)
        if results:
            summary_lines = [f"- {item.title}: {item.content[:150]}" for item in results[:3]]
            response_text = "\n".join(summary_lines)
            with timer.stage("ui_spec_build"):
                ui_spec = await self._dynamic_ui.generate_ui_spec("knowledge", results)
            sources = [item.model_dump() for item in results]

            # S5-11: 写入语义缓存
            with timer.stage("semantic_cache_store"):
                await self._semantic_cache.store(
                    question=req.message,
                    answer=response_text,
                    sources=sources,
                    ui_spec=ui_spec,
                )
        else:
            response_text = "未从知识库中检索到相关内容。"
            ui_spec = None
            sources = []
        timer.log_summary("handle_knowledge")
        return {"response_text": response_text, "ui_spec": ui_spec, "sources": sources}

    async def _handle_query(self, state: ChatState) -> dict[str, Any]:
        """问数节点，统一走 `Text2SQLService` 门面。"""
        req = ChatRequest(**state["request"])
        result = await self._text2sql_service.query(
            req.message,
            sub_intent=state.get("sub_intent"),
            conversation_id=req.conversation_id,
            context=req.context,
        )
        ui_spec = result.chart_spec or await self._dynamic_ui.generate_ui_spec(
            "query", result.results, {"question": req.message}
        )
        sources = [{"sql": result.sql}]
        return {"response_text": result.answer or result.explanation, "ui_spec": ui_spec, "sources": sources}

    async def _handle_task(self, state: ChatState) -> dict[str, Any]:
        """待办节点。

        功能：
            通过 business-server 聚合接口查询用户待办，并转换为可渲染的任务工作台。
        """
        req = ChatRequest(**state["request"])
        tasks: list[dict[str, Any]] = []
        try:
            url = f"{settings.business_server_url}/api/v1/tasks/aggregate"
            token = None
            if req.context and isinstance(req.context, dict):
                token = req.context.get("token")
            headers: dict[str, str] = {}
            if token:
                headers["Authorization"] = f"Bearer {token}"
            resp = await self._http.get(
                url,
                params={"userId": req.user_id, "page": 1, "size": 20},
                headers=headers,
            )
            if resp.status_code == 200:
                body = resp.json()
                data = body.get("data", body)
                if isinstance(data, dict) and "records" in data:
                    tasks = data["records"]
                elif isinstance(data, list):
                    tasks = data
        except Exception as exc:
            logger.warning("Failed to fetch tasks from business server: %s", exc)

        if tasks:
            count = len(tasks)
            response_text = f"为您查询到 {count} 条待办任务："
            for i, t in enumerate(tasks[:5], 1):
                title = t.get("title", "未命名任务")
                status = t.get("status", "")
                source = t.get("sourceSystem", "")
                response_text += f"\n{i}. [{source}] {title}（{status}）"
            if count > 5:
                response_text += f"\n...还有 {count - 5} 条"
            ui_spec = await self._dynamic_ui.generate_ui_spec("task", tasks)
        else:
            response_text = "暂无待办任务，您的待办清单是空的。"
            ui_spec = None

        return {"response_text": response_text, "ui_spec": ui_spec, "sources": []}

    async def _handle_chat(self, state: ChatState) -> dict[str, Any]:
        """兜底闲聊节点。"""
        req = ChatRequest(**state["request"])
        reply = await self._llm_service.chat(
            messages=[{"role": "user", "content": req.message}],
        )
        return {"response_text": reply, "ui_spec": None, "sources": []}

    def _route_intent(self, state: ChatState) -> IntentType | str:
        """将分类结果映射为状态图分支。"""
        intent = state.get("intent", IntentType.CHAT)
        return intent if isinstance(intent, IntentType) else IntentType.CHAT

    def _to_response(self, request: ChatRequest, state: ChatState) -> ChatResponse:
        """把图内状态转换为对外响应模型。"""
        intent = state.get("intent", IntentType.CHAT)
        if not isinstance(intent, IntentType) and intent:
            intent = IntentType(intent)
        elif not intent:
            intent = IntentType.CHAT
        conversation_id = request.conversation_id or str(uuid4())
        return ChatResponse(
            conversation_id=conversation_id,
            intent=intent,
            content=state.get("response_text", ""),
            ui_spec=state.get("ui_spec"),
            sources=state.get("sources", []),
        )

    @staticmethod
    def _sse(event_type: str, payload: Any, trace_id: str = "") -> str:
        """统一 SSE 信封格式 — STREAM_START / STREAM_CHUNK / STREAM_END / STREAM_ERROR"""
        envelope = {
            "version": "1.0",
            "id": str(uuid4()),
            "traceId": trace_id,
            "timestamp": int(time.time() * 1000),
            "source": "ai-gateway",
            "type": event_type,
            "payload": payload,
        }
        return f"event: {event_type}\ndata: {json.dumps(envelope, ensure_ascii=False)}\n\n"
