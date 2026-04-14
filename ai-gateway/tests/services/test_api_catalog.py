"""
Tests for API Catalog services.

Tests cover:
- ApiCatalogEntry.embed_text generation
- _extract_data: dot-notation path extraction
- _apply_field_labels: Chinese field renaming
- _validate_params: hallucination filtering
- _coerce_type: type coercion
"""

from __future__ import annotations

import asyncio
import json
import logging

import httpx
import pytest
from pymilvus import DataType

import app.services.api_catalog.indexer as indexer_module
from app.core.config import settings
from app.models.schemas import ApiQueryExecutionStatus
from app.services.api_catalog.executor import (
    ApiExecutor,
    LegacyApiExecutor,
    RuntimeInvokeExecutor,
    _apply_field_labels,
    _extract_data,
)
from app.services.api_catalog.indexer import _create_collection, _get_collection_schema
from app.services.api_catalog.param_extractor import _coerce_type, _parse_json, _validate_params
from app.services.api_catalog.retriever import (
    _LEGACY_OUTPUT_FIELDS,
    _build_entry_from_fields,
    _build_filter_expr,
    ApiCatalogRetriever,
)
from app.services.api_catalog.schema import (
    ApiCatalogEntry,
    ApiCatalogSearchFilters,
    ApiCatalogSearchResult,
    ParamSchema,
)


# ── schema tests ─────────────────────────────────────────────────────────────


class TestApiCatalogEntry:
    def _make_entry(self, **kwargs) -> ApiCatalogEntry:
        defaults = {
            "id": "test_api_v1",
            "description": "查询客户列表",
            "path": "/api/customer/list",
        }
        return ApiCatalogEntry(**{**defaults, **kwargs})

    def test_embed_text_includes_description(self):
        entry = self._make_entry(description="查询客户信息")
        assert "查询客户信息" in entry.embed_text

    def test_embed_text_includes_examples(self):
        entry = self._make_entry(example_queries=["我的客户", "名下客户列表"])
        assert "我的客户" in entry.embed_text
        assert "名下客户列表" in entry.embed_text

    def test_embed_text_includes_tags(self):
        entry = self._make_entry(tags=["CRM", "客户"])
        assert "CRM" in entry.embed_text

    def test_default_values(self):
        entry = self._make_entry()
        assert entry.method == "GET"
        assert entry.auth_required is True
        assert entry.ui_hint == "table"
        assert entry.response_data_path == "data"
        assert entry.domain == "generic"
        assert entry.env == "shared"
        assert entry.status == "active"
        assert entry.business_intents == ["query_business_data"]
        assert entry.operation_safety == "mutation"
        assert entry.requires_confirmation is False
        assert entry.request_field_profiles == []
        assert entry.response_field_profiles == []

    def test_embed_text_includes_registry_fields(self):
        entry = self._make_entry(domain="crm", tag_name="customer_management", business_intents=["query_business_data"])
        assert "domain:crm" in entry.embed_text
        assert "customer_management" in entry.embed_text
        assert "query_business_data" in entry.embed_text

    def test_api_schema_contains_request_response_and_sample_request(self):
        entry = self._make_entry(
            param_schema=ParamSchema(
                type="object",
                properties={"pageNum": {"type": "integer"}},
                required=["pageNum"],
            ),
            response_schema={"type": "object", "properties": {"data": {"type": "array"}}},
            sample_request={"pageNum": 1},
            response_data_path="data.list",
            field_labels={"customerId": "客户ID"},
        )

        assert entry.api_schema == {
            "request": {
                "type": "object",
                "properties": {"pageNum": {"type": "integer"}},
                "required": ["pageNum"],
            },
            "response_schema": {"type": "object", "properties": {"data": {"type": "array"}}},
            "sample_request": {"pageNum": 1},
            "response_data_path": "data.list",
            "field_labels": {"customerId": "客户ID"},
        }


# ── executor _extract_data tests ─────────────────────────────────────────────


class TestExtractData:
    def test_simple_data_path(self):
        body = {"data": [{"id": 1}, {"id": 2}]}
        data, total = _extract_data(body, "data")
        assert len(data) == 2
        assert total == 2

    def test_nested_data_path(self):
        body = {"data": {"list": [{"id": 1}], "total": 100}}
        data, total = _extract_data(body, "data.list")
        assert len(data) == 1
        assert total == 100

    def test_total_from_parent(self):
        body = {"data": {"list": [{"id": i} for i in range(5)], "total": 50, "totalCount": 50}}
        data, total = _extract_data(body, "data.list")
        assert total == 50

    def test_dict_response(self):
        body = {"data": {"orderId": 1, "amount": 100.0}}
        data, total = _extract_data(body, "data")
        assert isinstance(data, dict)
        assert total == 1

    def test_fallback_on_wrong_path(self):
        # data_path doesn't match, should fall back to "data" key
        body = {"data": [{"id": 1}]}
        data, total = _extract_data(body, "wrong.path")
        assert len(data) == 1

    def test_none_payload_becomes_empty_result(self):
        body = {"data": None}
        data, total = _extract_data(body, "data")
        assert data == []
        assert total == 0


class TestApplyFieldLabels:
    def test_renames_fields(self):
        data = [{"customerId": 1, "customerName": "张三"}]
        labels = {"customerId": "客户ID", "customerName": "客户姓名"}
        result = _apply_field_labels(data, labels)
        assert result[0]["客户ID"] == 1
        assert result[0]["客户姓名"] == "张三"

    def test_unknown_fields_kept_as_is(self):
        data = [{"unknownField": "value"}]
        labels = {"customerId": "客户ID"}
        result = _apply_field_labels(data, labels)
        assert result[0]["unknownField"] == "value"

    def test_empty_labels_returns_unchanged(self):
        data = [{"id": 1}]
        result = _apply_field_labels(data, {})
        assert result == data

    def test_dict_input(self):
        data = {"totalAmount": 1000.0}
        labels = {"totalAmount": "总金额"}
        result = _apply_field_labels(data, labels)
        assert result["总金额"] == 1000.0


class TestApiExecutorGuard:
    @pytest.mark.asyncio
    async def test_call_blocks_non_get_method_before_sending_request(self):
        """执行器默认只允许 GET，避免查询链路因为上层漏校验而误打写请求。"""

        entry = ApiCatalogEntry(
            id="customer_delete",
            description="删除客户",
            method="DELETE",
            path="/api/customer/delete",
        )
        request_sent = False

        async def fail_if_called(_: httpx.Request) -> httpx.Response:
            nonlocal request_sent
            request_sent = True
            raise AssertionError("非 GET 方法不应该真正发出 HTTP 请求。")

        executor = ApiExecutor()
        executor._client = httpx.AsyncClient(
            transport=httpx.MockTransport(fail_if_called),
            base_url="http://testserver",
        )
        result = await executor.call(
            entry,
            {"customerId": "C001"},
            trace_id="trace_executor_guard",
        )

        assert request_sent is False
        assert result.status == "ERROR"
        assert result.error_code == "EXECUTOR_METHOD_NOT_ALLOWED"
        assert result.retryable is False
        assert "DELETE /api/customer/delete" in (result.error or "")

        await executor.close()

    def test_resolve_executor_infers_runtime_invoke_for_stale_registry_entry(self, monkeypatch):
        """旧索引缺少 executor_type 时，普通注册表条目也应切到 runtime invoke。"""

        monkeypatch.setattr(settings, "api_query_runtime_enabled", True)
        legacy_executor = LegacyApiExecutor()
        runtime_executor = RuntimeInvokeExecutor()
        executor = ApiExecutor(
            legacy_executor=legacy_executor,
            runtime_executor=runtime_executor,
        )

        entry = ApiCatalogEntry(
            id="customer_list",
            description="查询客户列表",
            operation_safety="query",
            method="GET",
            path="/api/customer/list",
            executor_config={"base_url": "https://beta-crm.ssss818.com/tapi/api/"},
        )

        resolved_executor, executor_type = executor._resolve_executor(entry)

        assert resolved_executor is runtime_executor
        assert executor_type == "runtime_invoke"

    def test_resolve_executor_keeps_builtin_entry_on_legacy_path(self, monkeypatch):
        """builtin 条目即使没有显式 executor_type，也不能被误判成 runtime invoke。"""

        monkeypatch.setattr(settings, "api_query_runtime_enabled", True)
        legacy_executor = LegacyApiExecutor()
        runtime_executor = RuntimeInvokeExecutor()
        executor = ApiExecutor(
            legacy_executor=legacy_executor,
            runtime_executor=runtime_executor,
        )

        entry = ApiCatalogEntry(
            id="system_dicts_v1",
            description="系统字典",
            operation_safety="query",
            method="GET",
            path="/api/system/dicts",
            executor_config={"source_id": "builtin"},
        )

        resolved_executor, executor_type = executor._resolve_executor(entry)

        assert resolved_executor is legacy_executor
        assert executor_type == ""


class TestRuntimeInvokeExecutor:
    @pytest.mark.asyncio
    async def test_call_puts_get_params_into_query_params_and_keeps_reserved_id(self, monkeypatch):
        captured: dict[str, object] = {}

        async def handler(request: httpx.Request) -> httpx.Response:
            captured["url"] = str(request.url)
            captured["json"] = json.loads(request.content.decode())
            captured["x_user_id"] = request.headers.get("X-User-Id")
            captured["authorization"] = request.headers.get("Authorization")
            return httpx.Response(
                200,
                json={
                    "code": 200,
                    "message": "success",
                    "data": {"data": {"list": [{"customerId": "C001"}], "total": 1}},
                },
            )

        monkeypatch.setattr(
            settings,
            "api_query_runtime_invoke_url_template",
            "http://runtime.example/ui-builder/runtime/endpoints/{id}/invoke",
        )
        monkeypatch.setattr(settings, "api_query_runtime_created_by", "gateway")

        executor = RuntimeInvokeExecutor()
        executor._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

        entry = ApiCatalogEntry(
            id="customer_list",
            description="查询客户列表",
            operation_safety="query",
            method="GET",
            path="/api/customer/list",
            response_data_path="data.list",
        )
        result = await executor.call(
            entry,
            {"id": "business-side-value", "pageNum": 1},
            user_token="Bearer token",
            user_id="header-user-001",
            trace_id="trace-runtime-get",
        )

        assert captured["url"] == "http://runtime.example/ui-builder/runtime/endpoints/customer_list/invoke"
        assert captured["json"] == {
            "flowNum": "trace-runtime-get",
            "queryParams": {"id": "business-side-value", "pageNum": 1},
            "createdBy": "header-user-001",
            "body": {},
        }
        assert captured["x_user_id"] == "header-user-001"
        assert captured["authorization"] == "Bearer token"
        assert result.status == ApiQueryExecutionStatus.SUCCESS
        assert result.data == [{"customerId": "C001"}]
        assert result.total == 1

        await executor.close()

    @pytest.mark.asyncio
    async def test_call_puts_post_params_into_body_and_unwraps_runtime_response(self, monkeypatch):
        captured: dict[str, object] = {}

        async def handler(request: httpx.Request) -> httpx.Response:
            captured["json"] = json.loads(request.content.decode())
            captured["x_user_id"] = request.headers.get("X-User-Id")
            return httpx.Response(
                200,
                json={
                    "code": 200,
                    "message": "success",
                    "data": {"payload": {"records": [{"customerId": "C002", "orderCount": 3}], "total": 1}},
                },
            )

        monkeypatch.setattr(
            settings,
            "api_query_runtime_invoke_url_template",
            "http://runtime.example/ui-builder/runtime/endpoints/{id}/invoke",
        )
        monkeypatch.setattr(settings, "api_query_runtime_created_by", "")

        executor = RuntimeInvokeExecutor()
        executor._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

        entry = ApiCatalogEntry(
            id="order_stats",
            description="查询订单统计",
            operation_safety="query",
            method="POST",
            path="/api/orders/stats",
            response_data_path="payload.records",
            field_labels={"customerId": "客户ID", "orderCount": "订单数"},
        )
        result = await executor.call(
            entry,
            {"customerId": "C002", "filters": {"level": "A"}},
            user_id="header-user-002",
            trace_id="trace-runtime-post",
        )

        assert captured["json"] == {
            "flowNum": "trace-runtime-post",
            "queryParams": {},
            "createdBy": "header-user-002",
            "body": {"customerId": "C002", "filters": {"level": "A"}},
        }
        assert captured["x_user_id"] == "header-user-002"
        assert result.status == ApiQueryExecutionStatus.SUCCESS
        assert result.data == [{"客户ID": "C002", "订单数": 3}]
        assert result.total == 1

        await executor.close()

    @pytest.mark.asyncio
    async def test_call_does_not_send_x_user_id_header_when_user_id_missing(self, monkeypatch):
        captured: dict[str, object] = {}

        async def handler(request: httpx.Request) -> httpx.Response:
            captured["x_user_id"] = request.headers.get("X-User-Id")
            captured["json"] = json.loads(request.content.decode())
            return httpx.Response(
                200,
                json={
                    "code": 200,
                    "message": "success",
                    "data": {"data": {"list": [{"customerId": "C003"}], "total": 1}},
                },
            )

        monkeypatch.setattr(
            settings,
            "api_query_runtime_invoke_url_template",
            "http://runtime.example/ui-builder/runtime/endpoints/{id}/invoke",
        )
        monkeypatch.setattr(settings, "api_query_runtime_created_by", "gateway")

        executor = RuntimeInvokeExecutor()
        executor._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

        entry = ApiCatalogEntry(
            id="customer_detail",
            description="查询客户详情",
            operation_safety="query",
            method="GET",
            path="/api/customer/detail",
            response_data_path="data.list",
        )
        result = await executor.call(
            entry,
            {"customerId": "C003"},
            trace_id="trace-runtime-without-user-id",
        )

        assert captured["x_user_id"] is None
        assert captured["json"] == {
            "flowNum": "trace-runtime-without-user-id",
            "queryParams": {"customerId": "C003"},
            "createdBy": "gateway",
            "body": {},
        }
        assert result.status == ApiQueryExecutionStatus.SUCCESS

        await executor.close()

    @pytest.mark.asyncio
    async def test_call_retries_without_x_user_id_when_primary_response_is_5xx(self, monkeypatch):
        captured_requests: list[dict[str, object]] = []
        call_count = 0

        async def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            captured_requests.append(
                {
                    "x_user_id": request.headers.get("X-User-Id"),
                    "authorization": request.headers.get("Authorization"),
                    "json": json.loads(request.content.decode()),
                }
            )
            if call_count == 1:
                return httpx.Response(500, json={"code": 500, "message": "系统内部错误，请稍后重试"})
            return httpx.Response(
                200,
                json={
                    "code": 200,
                    "message": "success",
                    "data": {"data": {"list": [{"customerId": "C004"}], "total": 1}},
                },
            )

        monkeypatch.setattr(
            settings,
            "api_query_runtime_invoke_url_template",
            "http://runtime.example/ui-builder/runtime/endpoints/{id}/invoke",
        )
        monkeypatch.setattr(settings, "api_query_runtime_created_by", "gateway")

        executor = RuntimeInvokeExecutor()
        executor._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        entry = ApiCatalogEntry(
            id="customer_retry",
            description="查询客户详情",
            operation_safety="query",
            method="GET",
            path="/api/customer/detail/{id}",
            response_data_path="data.list",
        )
        result = await executor.call(
            entry,
            {"id": "C004"},
            user_token="Bearer token",
            user_id="hello",
            trace_id="trace-runtime-fallback",
        )

        assert call_count == 2
        assert captured_requests[0]["x_user_id"] == "hello"
        assert captured_requests[0]["authorization"] == "Bearer token"
        assert captured_requests[1]["x_user_id"] is None
        assert captured_requests[1]["authorization"] == "Bearer token"
        assert captured_requests[0]["json"] == captured_requests[1]["json"]
        assert result.status == ApiQueryExecutionStatus.SUCCESS
        assert result.data == [{"customerId": "C004"}]
        assert result.total == 1

        await executor.close()


# ── param_extractor utils tests ──────────────────────────────────────────────


class TestCoerceType:
    def test_string_to_integer(self):
        assert _coerce_type("5", "integer") == 5

    def test_string_to_float(self):
        assert _coerce_type("3.14", "number") == 3.14

    def test_string_true_to_boolean(self):
        assert _coerce_type("true", "boolean") is True

    def test_string_false_to_boolean(self):
        assert _coerce_type("0", "boolean") is False

    def test_invalid_keeps_original(self):
        # Can't coerce "abc" to integer, should return original
        result = _coerce_type("abc", "integer")
        assert result == "abc"


class TestParseJson:
    def test_plain_json(self):
        assert _parse_json('{"name": "张"}') == {"name": "张"}

    def test_markdown_code_block(self):
        text = '```json\n{"name": "张"}\n```'
        assert _parse_json(text) == {"name": "张"}

    def test_invalid_returns_empty(self):
        assert _parse_json("not json at all") == {}


class TestValidateParams:
    def _make_entry(self, properties: dict) -> ApiCatalogEntry:
        return ApiCatalogEntry(
            id="test",
            description="test",
            path="/test",
            param_schema=ParamSchema(type="object", properties=properties),
        )

    def test_filters_hallucinated_keys(self):
        entry = self._make_entry({"name": {"type": "string"}})
        params = {"name": "张三", "hackerField": "evil"}
        result = _validate_params(params, entry)
        assert "hackerField" not in result
        assert result["name"] == "张三"

    def test_type_coercion(self):
        entry = self._make_entry({"pageNum": {"type": "integer"}})
        params = {"pageNum": "2"}
        result = _validate_params(params, entry)
        assert result["pageNum"] == 2

    def test_empty_schema_passes_through(self):
        entry = ApiCatalogEntry(id="t", description="t", path="/t")
        params = {"anything": "value"}
        assert _validate_params(params, entry) == params


class TestRetrieverFilters:
    def test_build_filter_expr(self):
        filters = ApiCatalogSearchFilters(
            domains=["crm"], envs=["shared"], statuses=["active"], tag_names=["customer_management"]
        )
        expr = _build_filter_expr(filters)
        assert expr == (
            'domain in ["crm"] and env in ["shared"] and status in ["active"] and tag_name in ["customer_management"]'
        )

    def test_build_filter_expr_from_dict(self):
        expr = _build_filter_expr({"domains": ["report"], "statuses": ["active"]})
        assert expr == 'domain in ["report"] and status in ["active"]'

    def test_search_stratified_keeps_each_domain_candidates(self, monkeypatch):
        retriever = ApiCatalogRetriever()

        async def fake_encode_query(query: str):
            return [0.1, 0.2]

        async def fake_search_domain_with_timeout(**kwargs):
            domain = kwargs["domain"]
            return [
                ApiCatalogSearchResult(
                    entry=ApiCatalogEntry(
                        id=f"{domain}_list",
                        description=f"{domain} list",
                        domain=domain,
                        path=f"/api/{domain}/list",
                    ),
                    score=0.91,
                )
            ]

        monkeypatch.setattr(retriever, "_encode_query", fake_encode_query)
        monkeypatch.setattr(retriever, "_search_domain_with_timeout", fake_search_domain_with_timeout)

        results = asyncio.run(
            retriever.search_stratified(
                "对比客户和订单",
                domains=["crm", "erp"],
                top_k=3,
                filters=ApiCatalogSearchFilters(statuses=["active"]),
            )
        )

        assert [result.entry.domain for result in results] == ["crm", "erp"]

    def test_search_stratified_skips_exceptional_domain_and_keeps_others(self, monkeypatch):
        retriever = ApiCatalogRetriever()

        async def fake_encode_query(query: str):
            return [0.1, 0.2]

        async def fake_search_domain_with_timeout(**kwargs):
            domain = kwargs["domain"]
            if domain == "erp":
                raise RuntimeError("milvus worker crashed")
            return [
                ApiCatalogSearchResult(
                    entry=ApiCatalogEntry(
                        id=f"{domain}_list",
                        description=f"{domain} list",
                        domain=domain,
                        path=f"/api/{domain}/list",
                    ),
                    score=0.91,
                )
            ]

        monkeypatch.setattr(retriever, "_encode_query", fake_encode_query)
        monkeypatch.setattr(retriever, "_search_domain_with_timeout", fake_search_domain_with_timeout)

        results = asyncio.run(
            retriever.search_stratified(
                "对比客户和订单",
                domains=["crm", "erp"],
                top_k=3,
                filters=ApiCatalogSearchFilters(statuses=["active"]),
            )
        )

        assert [result.entry.domain for result in results] == ["crm"]

    def test_search_domain_with_timeout_returns_empty_when_single_domain_hangs(self, monkeypatch):
        retriever = ApiCatalogRetriever()
        monkeypatch.setattr(settings, "api_query_retrieval_timeout_seconds", 0.01)

        async def fake_search_with_embedding(**kwargs):
            await asyncio.sleep(0.05)
            return [
                ApiCatalogSearchResult(
                    entry=ApiCatalogEntry(id="crm_list", description="crm list", domain="crm", path="/api/crm/list"),
                    score=0.91,
                )
            ]

        monkeypatch.setattr(retriever, "_search_with_embedding", fake_search_with_embedding)

        results = asyncio.run(
            retriever._search_domain_with_timeout(
                query="查客户",
                query_emb=[0.1, 0.2],
                domain="crm",
                top_k=2,
                score_threshold=0.3,
                base_filters=ApiCatalogSearchFilters(statuses=["active"]),
            )
        )

        assert results == []

    def test_search_with_embedding_filters_low_score_hits(self, monkeypatch):
        retriever = ApiCatalogRetriever()

        class FakeEntity:
            def __init__(self, fields):
                self._fields = fields

            def get(self, key):
                return self._fields.get(key)

        class FakeHit:
            def __init__(self, score, fields):
                self.distance = score
                self.entity = FakeEntity(fields)

        class FakeCollection:
            def search(self, **kwargs):
                return [
                    [
                        FakeHit(
                            0.75,
                            {
                                "id": "crm_high",
                                "description": "高分客户查询",
                                "domain": "crm",
                                "env": "shared",
                                "status": "active",
                                "method": "GET",
                                "path": "/api/crm/high",
                                "auth_required": True,
                                "ui_hint": "table",
                                "api_schema": {"request": {"type": "object", "properties": {}}},
                            },
                        ),
                        FakeHit(
                            0.2,
                            {
                                "id": "crm_low",
                                "description": "低分噪声接口",
                                "domain": "crm",
                                "env": "shared",
                                "status": "active",
                                "method": "GET",
                                "path": "/api/crm/low",
                                "auth_required": True,
                                "ui_hint": "table",
                                "api_schema": {"request": {"type": "object", "properties": {}}},
                            },
                        ),
                    ]
                ]

        monkeypatch.setattr(retriever, "_get_collection", lambda: FakeCollection())
        monkeypatch.setattr(
            retriever,
            "_get_output_fields",
            lambda: [
                "id",
                "description",
                "domain",
                "env",
                "status",
                "method",
                "path",
                "auth_required",
                "ui_hint",
                "api_schema",
            ],
        )
        monkeypatch.setattr(retriever, "_get_search_param", lambda: {"metric_type": "COSINE", "params": {"ef": 64}})

        results = asyncio.run(
            retriever._search_with_embedding(
                query="查客户",
                query_emb=[0.1, 0.2],
                top_k=2,
                score_threshold=0.6,
                filters=ApiCatalogSearchFilters(domains=["crm"], statuses=["active"]),
            )
        )

        assert len(results) == 1
        assert results[0].entry.id == "crm_high"


class TestIndexerSchema:
    def test_collection_schema_uses_json_fields_and_dynamic_fields(self):
        schema = _get_collection_schema()
        field_map = {field.name: field for field in schema.fields}

        assert schema.enable_dynamic_field is True
        assert field_map["api_schema"].dtype == DataType.JSON
        assert field_map["executor_config"].dtype == DataType.JSON
        assert field_map["security_rules"].dtype == DataType.JSON
        assert field_map["example_queries"].dtype == DataType.JSON
        assert field_map["operation_safety"].dtype == DataType.VARCHAR

    def test_create_collection_uses_hnsw_and_scalar_indexes(self, monkeypatch):
        class FakeCollection:
            def __init__(self, name, schema):
                self.name = name
                self.schema = schema
                self.index_calls: list[tuple[str, dict]] = []
                self.loaded = False

            def create_index(self, field_name, index_params):
                self.index_calls.append((field_name, index_params))

            def load(self):
                self.loaded = True

        monkeypatch.setattr(indexer_module, "Collection", FakeCollection)

        collection = _create_collection()
        index_map = {field_name: params for field_name, params in collection.index_calls}

        assert index_map["embedding"] == {
            "metric_type": "COSINE",
            "index_type": "HNSW",
            "params": {"M": 16, "efConstruction": 200},
        }
        assert index_map["domain"] == {"index_type": "INVERTED"}
        assert index_map["env"] == {"index_type": "INVERTED"}
        assert index_map["status"] == {"index_type": "INVERTED"}
        assert index_map["tag_name"] == {"index_type": "INVERTED"}
        assert index_map["operation_safety"] == {"index_type": "INVERTED"}
        assert collection.loaded is True

    def test_get_collection_passes_timeout_to_milvus_connect(self, monkeypatch):
        captured: dict[str, object] = {}

        class FakeCollection:
            def __init__(self, name):
                self.name = name
                self.schema = type("FakeSchema", (), {"fields": _get_collection_schema().fields, "enable_dynamic_field": True})()
                self.loaded = False

            def load(self):
                self.loaded = True

        def fake_connect(**kwargs):
            captured["connect_kwargs"] = kwargs

        monkeypatch.setattr(settings, "milvus_host", "milvus.internal")
        monkeypatch.setattr(settings, "milvus_port", 19530)
        monkeypatch.setattr(settings, "api_catalog_milvus_connect_timeout_seconds", 4.5)
        monkeypatch.setattr(indexer_module.connections, "connect", fake_connect)
        monkeypatch.setattr(indexer_module.utility, "has_collection", lambda _: True)
        monkeypatch.setattr(indexer_module, "Collection", FakeCollection)

        collection = indexer_module.ApiCatalogIndexer()._get_collection()

        assert captured["connect_kwargs"] == {
            "alias": "default",
            "host": "milvus.internal",
            "port": 19530,
            "timeout": 4.5,
        }
        assert collection.loaded is True

    def test_configure_cli_logging_uses_info_in_debug_mode(self, monkeypatch):
        captured: dict[str, object] = {}

        def fake_basic_config(**kwargs):
            captured.update(kwargs)

        monkeypatch.setattr(settings, "app_debug", True)
        monkeypatch.setattr(indexer_module.logging, "basicConfig", fake_basic_config)

        indexer_module._configure_cli_logging()

        assert captured["level"] == logging.INFO
        assert captured["force"] is True

    def test_indexer_prefers_local_embedding_model_path(self, monkeypatch, tmp_path):
        captured: dict[str, object] = {}
        model_dir = tmp_path / "BAAI" / "bge-m3"
        model_dir.mkdir(parents=True)

        class FakeBGEM3FlagModel:
            def __init__(self, source: str, use_fp16: bool) -> None:
                captured["source"] = source
                captured["use_fp16"] = use_fp16

        fake_module = type("FakeFlagEmbeddingModule", (), {"BGEM3FlagModel": FakeBGEM3FlagModel})

        monkeypatch.setattr(settings, "embedding_model_name", "BAAI/bge-m3")
        monkeypatch.setattr(settings, "embedding_model_path", str(model_dir))
        monkeypatch.setattr(indexer_module.importlib, "import_module", lambda name: fake_module)

        indexer = indexer_module.ApiCatalogIndexer()
        indexer._get_embedder()

        assert captured["source"] == str(model_dir.resolve())
        assert captured["use_fp16"] is True

    def test_indexer_falls_back_to_embedding_model_name_when_local_path_is_invalid(self, monkeypatch, tmp_path):
        captured: dict[str, object] = {}
        missing_dir = tmp_path / "missing-bge-m3"

        class FakeBGEM3FlagModel:
            def __init__(self, source: str, use_fp16: bool) -> None:
                captured["source"] = source
                captured["use_fp16"] = use_fp16

        fake_module = type("FakeFlagEmbeddingModule", (), {"BGEM3FlagModel": FakeBGEM3FlagModel})

        monkeypatch.setattr(settings, "embedding_model_name", "BAAI/bge-m3")
        monkeypatch.setattr(settings, "embedding_model_path", str(missing_dir))
        monkeypatch.setattr(indexer_module.importlib, "import_module", lambda name: fake_module)

        indexer = indexer_module.ApiCatalogIndexer()
        indexer._get_embedder()

        assert captured["source"] == "BAAI/bge-m3"
        assert captured["use_fp16"] is True

    @pytest.mark.asyncio
    async def test_indexer_warms_up_embedder_only_once(self, monkeypatch):
        calls: list[list[str]] = []

        class FakeVector:
            def tolist(self) -> list[float]:
                return [0.1, 0.2]

        class FakeEmbedder:
            def encode(self, texts: list[str]) -> dict[str, list[FakeVector]]:
                calls.append(list(texts))
                return {"dense_vecs": [FakeVector()]}

        indexer = indexer_module.ApiCatalogIndexer()
        monkeypatch.setattr(indexer, "_get_embedder", lambda: FakeEmbedder())

        await indexer._ensure_embedder_warmed_up()
        await indexer._ensure_embedder_warmed_up()

        assert calls == [["api catalog warmup"]]

    @pytest.mark.asyncio
    async def test_index_entry_warms_up_before_connecting_milvus(self, monkeypatch):
        order: list[str] = []

        class FakeVector:
            def tolist(self) -> list[float]:
                return [0.1, 0.2]

        class FakeEmbedder:
            def encode(self, texts: list[str]) -> dict[str, list[FakeVector]]:
                text = texts[0]
                if text == "api catalog warmup":
                    order.append("warmup")
                else:
                    order.append("entry_encode")
                return {"dense_vecs": [FakeVector()]}

        class FakeCollection:
            def delete(self, expr: str) -> None:
                order.append("collection_delete")

            def insert(self, data) -> None:
                order.append("collection_insert")

            def flush(self) -> None:
                order.append("collection_flush")

        indexer = indexer_module.ApiCatalogIndexer()
        fake_embedder = FakeEmbedder()
        fake_collection = FakeCollection()

        monkeypatch.setattr(indexer, "_get_embedder", lambda: fake_embedder)
        monkeypatch.setattr(indexer, "_get_collection", lambda: order.append("collection_connect") or fake_collection)

        await indexer.index_entry(
            ApiCatalogEntry(
                id="customer_list",
                description="查询客户列表",
                domain="crm",
                method="GET",
                path="/api/v1/customers",
            )
        )

        assert order[:3] == ["warmup", "collection_connect", "entry_encode"]


class TestRetrieverCompatibility:
    def test_build_entry_from_fields_supports_native_json_schema(self):
        entry = _build_entry_from_fields(
            {
                "id": "customer_list",
                "description": "查询客户列表",
                "domain": "crm",
                "env": "prod",
                "status": "active",
                "tag_name": "客户管理",
                "operation_safety": "query",
                "method": "GET",
                "path": "/api/customer/list",
                "auth_required": True,
                "ui_hint": "table",
                "example_queries": ["查询客户列表"],
                "tags": ["客户管理", "crm"],
                "business_intents": ["query_business_data"],
                "api_schema": {
                    "request": {
                        "type": "object",
                        "properties": {"pageNum": {"type": "integer"}},
                        "required": ["pageNum"],
                    },
                    "response_schema": {"type": "object", "properties": {"data": {"type": "array"}}},
                    "sample_request": {"pageNum": 1},
                    "response_data_path": "data.list",
                    "field_labels": {"customerId": "客户ID"},
                },
                "field_labels": {"customerId": "客户ID"},
                "executor_config": {"base_url": "http://business-server"},
                "security_rules": {"read_only": True},
                "requires_confirmation": False,
                "detail_hint": {"enabled": False},
                "pagination_hint": {"enabled": True, "page_param": "pageNum"},
                "template_hint": {"enabled": False},
            }
        )

        assert entry.param_schema.required == ["pageNum"]
        assert entry.response_schema["type"] == "object"
        assert entry.sample_request == {"pageNum": 1}
        assert entry.field_labels["customerId"] == "客户ID"
        assert entry.operation_safety == "query"
        assert entry.requires_confirmation is False

    def test_build_entry_from_fields_infers_requires_confirmation_for_legacy_mutation_record(self):
        entry = _build_entry_from_fields(
            {
                "id": "role_delete",
                "description": "删除角色",
                "domain": "iam",
                "env": "prod",
                "status": "active",
                "operation_safety": "mutation",
                "method": "POST",
                "path": "/system/employee/sys-role/delete",
                "auth_required": True,
                "ui_hint": "table",
                "example_queries": [],
                "tags": [],
                "business_intents": ["query_business_data"],
                "api_schema": {"request": {"type": "object", "properties": {}}, "response_schema": {}},
                "security_rules": {"operation_safety": "mutation"},
            }
        )

        assert entry.requires_confirmation is True

    def test_retriever_uses_legacy_output_fields_before_reindex(self):
        retriever = ApiCatalogRetriever()

        class FakeField:
            def __init__(self, name: str) -> None:
                self.name = name

        class FakeSchema:
            fields = [FakeField(name) for name in _LEGACY_OUTPUT_FIELDS]

        class FakeCollection:
            def __init__(self) -> None:
                self.schema = FakeSchema()

            def load(self) -> None:
                return None

        retriever._collection = FakeCollection()

        assert retriever._get_output_fields() == _LEGACY_OUTPUT_FIELDS
        assert retriever._get_search_param() == {"metric_type": "IP", "params": {"nprobe": 16}}
