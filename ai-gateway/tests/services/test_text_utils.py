from __future__ import annotations

from app.utils.text_utils import normalize_scalar_text, normalize_text, normalize_text_or_none


def test_normalize_text_returns_stable_blank_string() -> None:
    assert normalize_text(None) == ""
    assert normalize_text("  abc  ") == "abc"
    assert normalize_text("nan") == ""
    assert normalize_text(123) == "123"


def test_normalize_text_or_none_collapses_blank_values() -> None:
    assert normalize_text_or_none(None) is None
    assert normalize_text_or_none("  ") is None
    assert normalize_text_or_none(" value ") == "value"


def test_normalize_scalar_text_rejects_container_values() -> None:
    assert normalize_scalar_text({"unexpected": "value"}) == ""
    assert normalize_scalar_text(["unexpected"]) == ""
    assert normalize_scalar_text(12.5) == "12.5"
