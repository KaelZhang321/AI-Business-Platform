from __future__ import annotations

from app.services.health_quadrant_repository import (
    _build_context_signature,
    _dump_canonical_complaints_json,
    _dump_canonical_items_json,
)


def test_context_signature_stable_for_array_and_object_order() -> None:
    items_variant_a = [
        {"itemId": "B-02", "itemText": "甲状腺结节"},
        {"itemText": "维生素D缺乏", "itemId": "A-01"},
    ]
    items_variant_b = [
        {"itemText": "维生素D缺乏", "itemId": "A-01"},
        {"itemText": "甲状腺结节", "itemId": "B-02"},
    ]
    complaints_variant_a = ["夜间易醒", "睡眠障碍"]
    complaints_variant_b = ["睡眠障碍", "夜间易醒"]

    sig_a = _build_context_signature(
        study_id="S1001",
        quadrant_type="exam",
        single_exam_items_json=_dump_canonical_items_json(items_variant_a),
        chief_complaint_items_json=_dump_canonical_complaints_json(complaints_variant_a),
        source_jlrq="2026-04-15 10:00:00",
        source_zjrq="2026-04-15 11:00:00",
    )
    sig_b = _build_context_signature(
        study_id="S1001",
        quadrant_type="exam",
        single_exam_items_json=_dump_canonical_items_json(items_variant_b),
        chief_complaint_items_json=_dump_canonical_complaints_json(complaints_variant_b),
        source_jlrq="2026-04-15 10:00:00",
        source_zjrq="2026-04-15 11:00:00",
    )

    assert sig_a == sig_b


def test_context_signature_changes_when_source_timestamps_change() -> None:
    base_kwargs = {
        "study_id": "S1001",
        "quadrant_type": "exam",
        "single_exam_items_json": _dump_canonical_items_json(
            [
                {"itemId": "A-01", "itemText": "维生素D缺乏"},
            ]
        ),
        "chief_complaint_items_json": _dump_canonical_complaints_json(["睡眠障碍"]),
    }

    sig_a = _build_context_signature(
        **base_kwargs,
        source_jlrq="2026-04-15 10:00:00",
        source_zjrq="2026-04-15 11:00:00",
    )
    sig_b = _build_context_signature(
        **base_kwargs,
        source_jlrq="2026-04-16 10:00:00",
        source_zjrq="2026-04-15 11:00:00",
    )
    sig_c = _build_context_signature(
        **base_kwargs,
        source_jlrq="2026-04-15 10:00:00",
        source_zjrq="2026-04-16 11:00:00",
    )

    assert sig_a != sig_b
    assert sig_a != sig_c
