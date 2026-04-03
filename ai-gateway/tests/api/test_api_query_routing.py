from __future__ import annotations

import asyncio

from app.services.api_catalog.param_extractor import (
    ApiParamExtractor,
    _parse_json,
    _sanitize_business_intents,
    _sanitize_query_domains,
    _sanitize_route_domains,
)
from app.services.api_catalog.schema import ApiCatalogEntry, ApiCatalogSearchResult, ParamSchema


def _make_entry(**kwargs) -> ApiCatalogEntry:
    defaults = {
        "id": "customer_list",
        "description": "查询客户列表",
        "domain": "crm",
        "path": "/api/customer/list",
        "business_intents": ["query_business_data"],
        "param_schema": ParamSchema(
            type="object",
            properties={
                "pageNum": {"type": "integer"},
                "customerId": {"type": "string"},
            },
        ),
    }
    return ApiCatalogEntry(**{**defaults, **kwargs})


def test_parse_json_strips_prefix_and_markdown() -> None:
    raw = """好的，以下是结果：
```json
{"selected_api_id":"customer_list","params":{"pageNum":1}}
```"""
    assert _parse_json(raw) == {"selected_api_id": "customer_list", "params": {"pageNum": 1}}


def test_sanitize_business_intents_intersects_allowlist() -> None:
    result = _sanitize_business_intents(
        ["none", "delete_everything"],
        allowed={"none", "prepare_high_risk_change"},
        fallback=["none"],
    )
    assert result == ["none"]


def test_sanitize_query_domains_falls_back_to_selected_entry_domain() -> None:
    candidates = [
        ApiCatalogSearchResult(entry=_make_entry(domain="crm"), score=0.9),
        ApiCatalogSearchResult(entry=_make_entry(id="order_list", domain="order"), score=0.8),
    ]
    result = _sanitize_query_domains(["finance"], candidates, "crm")
    assert result == ["crm"]


def test_sanitize_route_domains_filters_unknown_and_normalizes_case() -> None:
    result = _sanitize_route_domains(["CRM", "meeting-bi", "unknown"])
    assert result == ["crm", "meeting_bi"]


def test_route_query_returns_fallback_when_llm_json_invalid(monkeypatch) -> None:
    extractor = ApiParamExtractor()

    async def fake_call_llm_json(prompt: str, *, scenario: str):
        return {}

    monkeypatch.setattr(extractor, "_call_llm_json", fake_call_llm_json)

    result = asyncio.run(
        extractor.route_query(
            "帮我处理下这个事情",
            {"userId": "u1"},
            allowed_business_intents={"none", "prepare_high_risk_change"},
        )
    )

    assert result.route_status == "fallback"
    assert result.route_error_code == "routing_parse_failed"
    assert result.business_intents == ["none"]


def test_extract_routing_result_falls_back_unknown_api_and_filters_params(monkeypatch) -> None:
    extractor = ApiParamExtractor()
    candidates = [
        ApiCatalogSearchResult(entry=_make_entry(), score=0.91),
        ApiCatalogSearchResult(entry=_make_entry(id="order_list", domain="order"), score=0.88),
    ]

    async def fake_call_llm_json(prompt: str, *, scenario: str):
        return {
            "selected_api_id": "unknown_api",
            "query_domains": ["finance"],
            "business_intents": ["query_business_data", "delete_everything"],
            "params": {"pageNum": "2", "hackerField": "boom"},
        }

    monkeypatch.setattr(extractor, "_call_llm_json", fake_call_llm_json)

    result = asyncio.run(
        extractor.extract_routing_result(
            "查询客户",
            candidates,
            {"userId": "u1"},
            allowed_business_intents={"none"},
            routing_hints=None,
        )
    )

    assert result.selected_api_id == "customer_list"
    assert result.query_domains == ["crm"]
    assert result.business_intents == ["none"]
    assert result.params == {"pageNum": 2}
