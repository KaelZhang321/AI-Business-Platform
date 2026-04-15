from __future__ import annotations

from app.utils.json_utils import (
    extract_first_json_object_text,
    load_json_object,
    load_json_object_or_none,
    load_json_value,
    parse_dirty_json_object,
    summarize_log_text,
)


def test_parse_dirty_json_object_handles_comments_code_fences_and_trailing_commas() -> None:
    raw = """```json
    {
      // 注释
      "root": "root",
      "state": {},
      "items": [
        1,
      ],
    }
    ```"""

    assert parse_dirty_json_object(raw) == {
        "root": "root",
        "state": {},
        "items": [1],
    }


def test_extract_first_json_object_text_returns_sanitized_json_object() -> None:
    raw = "说明前缀\n{\"name\":\"demo\",}\n说明后缀"

    assert extract_first_json_object_text(raw) == '{"name":"demo"}'


def test_load_json_value_and_object_variants_preserve_expected_defaults() -> None:
    assert load_json_value('["a", "b"]', []) == ["a", "b"]
    assert load_json_value("bad-json", {"fallback": True}) == {"fallback": True}
    assert load_json_object('{"name":"planner"}') == {"name": "planner"}
    assert load_json_object('["not-object"]', default={"safe": True}) == {"safe": True}
    assert load_json_object_or_none('{"enabled":true}') == {"enabled": True}
    assert load_json_object_or_none('["not-object"]') is None


def test_summarize_log_text_truncates_long_payload() -> None:
    long_text = "abc " * 100

    summarized = summarize_log_text(long_text, limit=20)

    assert summarized.endswith("...")
    assert len(summarized) <= 23
