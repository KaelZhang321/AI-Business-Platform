from __future__ import annotations

from app.services.api_catalog.schema_utils import (
    describe_schema_type,
    extract_schema_description,
    resolve_schema_at_data_path,
    schema_is_array,
)


def test_resolve_schema_at_data_path_enters_array_items() -> None:
    response_schema = {
        "type": "object",
        "properties": {
            "data": {
                "type": "object",
                "properties": {
                    "list": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "customerId": {"type": "string", "description": "客户ID"},
                            },
                        },
                    }
                },
            }
        },
    }

    resolved_schema, array_mode = resolve_schema_at_data_path(response_schema, "data.list")

    assert array_mode is True
    assert resolved_schema["properties"]["customerId"]["description"] == "客户ID"


def test_schema_utils_describe_type_and_description() -> None:
    field_schema = {
        "type": "array",
        "items": {"type": "integer"},
        "title": "客户编号列表",
    }

    assert describe_schema_type(field_schema) == "list<integer>"
    assert extract_schema_description(field_schema) == "客户编号列表"
    assert schema_is_array(field_schema) is True
