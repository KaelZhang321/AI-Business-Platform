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

import pytest

from app.services.api_catalog.executor import (
    ApiCallError,
    _apply_field_labels,
    _extract_data,
    _safe_json,
)
from app.services.api_catalog.param_extractor import _coerce_type, _parse_json, _validate_params
from app.services.api_catalog.retriever import _build_filter_expr
from app.services.api_catalog.schema import ApiCatalogEntry, ApiCatalogSearchFilters, ParamSchema


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
        entry = self._make_entry(
            example_queries=["我的客户", "名下客户列表"]
        )
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

    def test_embed_text_includes_registry_fields(self):
        entry = self._make_entry(domain="crm", tag_name="customer_management", business_intents=["query_business_data"])
        assert "domain:crm" in entry.embed_text
        assert "customer_management" in entry.embed_text
        assert "query_business_data" in entry.embed_text


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
        text = "```json\n{\"name\": \"张\"}\n```"
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
        filters = ApiCatalogSearchFilters(domains=["crm"], envs=["shared"], statuses=["active"], tag_names=["customer_management"])
        expr = _build_filter_expr(filters)
        assert expr == (
            'domain in ["crm"] and env in ["shared"] and status in ["active"] '
            'and tag_name in ["customer_management"]'
        )

    def test_build_filter_expr_from_dict(self):
        expr = _build_filter_expr({"domains": ["report"], "statuses": ["active"]})
        assert expr == 'domain in ["report"] and status in ["active"]'
