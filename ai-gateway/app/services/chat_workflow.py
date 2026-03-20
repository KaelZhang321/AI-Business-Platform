from __future__ import annotations

import json
from typing import Any, Literal, TypedDict
from uuid import uuid4

from langgraph.graph import END, StateGraph

from app.models.schemas import ChatRequest, ChatResponse, IntentType
from app.services.dynamic_ui_service import DynamicUIService
from app.services.intent_classifier import IntentClassifier
from app.services.llm_service import LLMService
from app.services.rag_service import RAGService
from app.services.text2sql_service import Text2SQLService


class ChatState(TypedDict, total=False):
    request: dict[str, Any]
    intent: IntentType | None
    response_text: str
    ui_spec: dict[str, Any] | None
    sources: list[dict[str, Any]]


class ChatWorkflow:
    """LangGraph workflow orchestrating intent classification and tool routing."""

    def __init__(
        self,
        *,
        intent_classifier: IntentClassifier | None = None,
        rag_service: RAGService | None = None,
        text2sql_service: Text2SQLService | None = None,
        dynamic_ui: DynamicUIService | None = None,
        llm_service: LLMService | None = None,
    ) -> None:
        self._intent_classifier = intent_classifier or IntentClassifier()
        self._rag_service = rag_service or RAGService()
        self._text2sql_service = text2sql_service or Text2SQLService()
        self._dynamic_ui = dynamic_ui or DynamicUIService()
        self._llm_service = llm_service or LLMService()
        self._graph = self._build_graph()

    def _build_graph(self):
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
        state = await self._graph.ainvoke(self._initial_state(request))
        return self._to_response(request, state)

    async def stream(self, request: ChatRequest):
        initial_state = self._initial_state(request)
        async for event in self._graph.astream_events(initial_state, version="v1"):
            yield from self._convert_event(request, event)

    def _convert_event(self, request: ChatRequest, event: dict[str, Any]):
        event_type: str | None = event.get("event")
        name: str | None = event.get("name")
        state = event.get("data", {}).get("state", {})

        if event_type == "on_node_end" and name == "classify":
            intent = state.get("intent", IntentType.CHAT)
            payload = {"intent": intent.value if isinstance(intent, IntentType) else intent}
            yield self._sse("intent", payload)
        elif event_type == "on_node_end" and name in {"knowledge", "query", "task", "chat"}:
            text = state.get("response_text", "")
            if text:
                yield self._sse("content", {"node": name, "text": text})
            if state.get("ui_spec"):
                yield self._sse("ui_spec", state["ui_spec"])
            if sources := state.get("sources"):
                yield self._sse("sources", sources)
        elif event_type == "on_graph_end":
            final_state = state if state else {}
            response = self._to_response(request, final_state)
            yield self._sse("done", response.model_dump())

    def _initial_state(self, request: ChatRequest) -> ChatState:
        return {
            "request": request.model_dump(),
            "intent": None,
            "response_text": "",
            "ui_spec": None,
            "sources": [],
        }

    async def _classify_intent(self, state: ChatState) -> dict[str, Any]:
        req = ChatRequest(**state["request"])
        intent = await self._intent_classifier.classify(req.message, req.context)
        return {"intent": intent}

    async def _handle_knowledge(self, state: ChatState) -> dict[str, Any]:
        req = ChatRequest(**state["request"])
        results = await self._rag_service.search(req.message)
        if results:
            summary_lines = [f"- {item.title}: {item.content[:150]}" for item in results[:3]]
            response_text = "\n".join(summary_lines)
            ui_spec = await self._dynamic_ui.generate_ui_spec("knowledge", results)
            sources = [item.model_dump() for item in results]
        else:
            response_text = "未从知识库中检索到相关内容。"
            ui_spec = None
            sources = []
        return {"response_text": response_text, "ui_spec": ui_spec, "sources": sources}

    async def _handle_query(self, state: ChatState) -> dict[str, Any]:
        req = ChatRequest(**state["request"])
        result = await self._text2sql_service.query(req.message)
        ui_spec = result.chart_spec or await self._dynamic_ui.generate_ui_spec("query", result.results, {"question": req.message})
        sources = [{"sql": result.sql}]
        return {"response_text": result.explanation, "ui_spec": ui_spec, "sources": sources}

    async def _handle_task(self, state: ChatState) -> dict[str, Any]:
        req = ChatRequest(**state["request"])
        return {
            "response_text": f"任务中心暂未开放自动操作，请前往工作台手动处理（用户 {req.user_id}）。",
            "ui_spec": None,
            "sources": [],
        }

    async def _handle_chat(self, state: ChatState) -> dict[str, Any]:
        req = ChatRequest(**state["request"])
        reply = await self._llm_service.chat(
            messages=[{"role": "user", "content": req.message}],
        )
        return {"response_text": reply, "ui_spec": None, "sources": []}

    def _route_intent(self, state: ChatState) -> IntentType | str:
        intent = state.get("intent", IntentType.CHAT)
        return intent if isinstance(intent, IntentType) else IntentType.CHAT

    def _to_response(self, request: ChatRequest, state: ChatState) -> ChatResponse:
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
    def _sse(event: str, data: Any) -> str:
        return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
