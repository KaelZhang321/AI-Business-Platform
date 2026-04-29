from __future__ import annotations

from typing import Any


def normalize_text(value: Any, *, treat_nan: bool = True) -> str:
    """Normalize arbitrary scalar text into a stable non-null string."""

    if value is None:
        return ""
    text = str(value).strip()
    if treat_nan and text.lower() == "nan":
        return ""
    return text


def normalize_scalar_text(value: Any, *, treat_nan: bool = True) -> str:
    """Normalize only primitive scalar values; reject containers as blank."""

    if value is None:
        return ""
    if not isinstance(value, (str, int, float)):
        return ""
    return normalize_text(value, treat_nan=treat_nan)


def normalize_text_or_none(value: Any, *, treat_nan: bool = True) -> str | None:
    """Normalize text and return None for blank values."""

    text = normalize_text(value, treat_nan=treat_nan)
    return text or None
