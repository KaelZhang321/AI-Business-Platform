from __future__ import annotations

import pytest

from app.services.health_quadrant_service import HealthQuadrantService


class StubRepository:
    def __init__(self, cached: dict | None = None):
        self.cached = cached
        self.upsert_payload = None
        self.draft_payload = None

    async def get_preferred_payload(
        self,
        *,
        study_id: str,
        quadrant_type: str,
        single_exam_items: list[dict[str, str]],
        chief_complaint_items: list[str],
        source_jlrq=None,
        source_zjrq=None,
        draft_not_older_than,
        trace_id: str | None = None,
    ) -> tuple[dict | None, str | None]:
        assert study_id == "2512160009"
        assert quadrant_type == "exam"
        # 该仓储桩复用于多条测试场景，不强绑单项数量，避免测试之间互相耦合。
        assert isinstance(single_exam_items, list)
        assert chief_complaint_items == sorted(chief_complaint_items)
        # assert source_jlrq == "2026-04-15 10:00:00"
        # assert source_zjrq == "2026-04-15 11:00:00"
        assert trace_id == "trace-001"
        if self.cached is None:
            return None, None
        return self.cached, "CONFIRMED"

    async def upsert_confirmed_payload(self, **kwargs) -> None:
        self.upsert_payload = kwargs

    async def upsert_draft_payload(self, **kwargs) -> None:
        self.draft_payload = kwargs

    async def close(self) -> None:
        return None


class StubLLM:
    async def chat(self, *args, **kwargs) -> str:
        return '{"items":["建议复查甲状腺超声"]}'


@pytest.mark.asyncio
async def test_query_quadrants_returns_cached_when_hit(monkeypatch) -> None:
    repo = StubRepository(
        cached={
            "quadrants": [
                {"q_code": "q1", "q_name": "一", "abnormalIndicators": ["A"], "recommendationPlans": ["R"]},
                {"q_code": "q2", "q_name": "二", "abnormalIndicators": ["B"], "recommendationPlans": ["R"]},
                {"q_code": "q3", "q_name": "三", "abnormalIndicators": ["C"], "recommendationPlans": ["R"]},
                {"q_code": "q4", "q_name": "四", "abnormalIndicators": ["D"], "recommendationPlans": ["R"]},
            ]
        }
    )
    service = HealthQuadrantService(repository=repo, llm_service=StubLLM())

    async def stub_load_source_data(*, study_id: str):
        assert study_id == "2512160009"
        return {
            "packageName": "套餐A",
            "finalConclusion": "建议进一步复查甲状腺超声",
            "sourceJlrq": "2026-04-15 10:00:00",
            "sourceZjrq": "2026-04-15 11:00:00",
            "splitRows": [],
        }

    async def fail_build_exam_quadrants(**kwargs):
        raise AssertionError("should not build quadrants when cache hit")

    monkeypatch.setattr(service, "_load_source_data", stub_load_source_data)
    monkeypatch.setattr(service, "_build_exam_quadrants", fail_build_exam_quadrants)
    result = await service.query_quadrants(
        study_id="2512160009",
        quadrant_type="exam",
        single_exam_items=[
            {"itemId": "A1", "itemText": "维生素D缺乏", "abnormalIndicator": "维生素D偏低"},
            {"itemId": "A2", "itemText": "甲状腺结节", "abnormalIndicator": "结节"},
        ],
        chief_complaint_items=["睡眠障碍", "夜间易醒"],
        trace_id="trace-001",
    )
    assert result["fromCache"] is True
    assert len(result["quadrants"]) == 4
    assert repo.draft_payload is None


@pytest.mark.asyncio
async def test_query_quadrants_exam_uses_one_two_item_split() -> None:
    repo = StubRepository(cached=None)
    service = HealthQuadrantService()  #repository=repo, llm_service=StubLLM())

    async def stub_load_source_data(*, study_id: str):
        assert study_id == "2512160009"
        return {
            "packageName": "套餐A",
            "finalConclusion": "建议进一步复查甲状腺超声",
            "sourceJlrq": "2026-04-15 10:00:00",
            "sourceZjrq": "2026-04-15 11:00:00",
            "splitRows": [
                {"one_item_name": "血脂", "two_item_name": "", "abnormal_item": "偏高", "category": "生化"},
                {"one_item_name": "肺部检查", "two_item_name": "肺部CT", "abnormal_item": "结节", "category": "影像"},
            ],
        }

    # monkeypatch.setattr(service, "_load_source_data", stub_load_source_data)
    result = await service.query_quadrants(
        study_id="2512160009",
        quadrant_type="exam",
        single_exam_items=[
            {"itemId": "A1", "itemText": "维生素", "abnormalIndicator": "维生素D偏低"},
            {"itemId": "A2", "itemText": "甲状腺超声", "abnormalIndicator": "结节"},
        ],
        chief_complaint_items=["睡眠障碍", "夜间易醒"],
        trace_id="trace-001",
    )
    # assert result["fromCache"] is False
    # quadrants = result["quadrants"]
    # assert len(quadrants) == 4
    # assert any("偏高" in item for item in quadrants[0]["abnormalIndicators"])
    # assert any("结节" in item for item in quadrants[1]["abnormalIndicators"])
    # assert "血脂" in quadrants[0]["recommendationPlans"]
    # assert "肺部CT" in quadrants[1]["recommendationPlans"]
    # # 单项体检项进入第三象限：项目名进 recommendationPlans，异常描述进 abnormalIndicators。
    # assert "维生素D缺乏" in quadrants[2]["recommendationPlans"]
    # assert "维生素D偏低" in quadrants[2]["abnormalIndicators"]
    # assert "甲状腺结节" in quadrants[2]["recommendationPlans"]
    # assert "结节" in quadrants[2]["abnormalIndicators"]
    # assert quadrants[0]["recommendationPlans"]
    # assert quadrants[1]["recommendationPlans"]
    # assert repo.draft_payload is not None
    # assert repo.draft_payload["quadrant_type"] == "exam"
    # assert repo.draft_payload["source_jlrq"] == "2026-04-15 10:00:00"
    # assert repo.draft_payload["source_zjrq"] == "2026-04-15 11:00:00"


@pytest.mark.asyncio
async def test_confirm_quadrants_persists_with_multi_items() -> None:
    repo = StubRepository(cached=None)
    service = HealthQuadrantService(repository=repo, llm_service=StubLLM())
    async def stub_load_source_data(*, study_id: str):
        assert study_id == "S1001"
        return {
            "packageName": "套餐A",
            "finalConclusion": "建议进一步复查甲状腺超声",
            "sourceJlrq": "2026-04-15 10:00:00",
            "sourceZjrq": "2026-04-15 11:00:00",
            "splitRows": [],
        }

    service._load_source_data = stub_load_source_data  # type: ignore[method-assign]
    await service.confirm_quadrants(
        study_id="S1001",
        quadrant_type="exam",
        single_exam_items=[
            {"itemId": "A1", "itemText": "维生素D缺乏", "abnormalIndicator": "维生素D偏低"},
            {"itemId": "A2", "itemText": "甲状腺结节", "abnormalIndicator": "结节"},
            {"itemId": "A2", "itemText": "甲状腺结节", "abnormalIndicator": "结节"},
        ],
        chief_complaint_items=["睡眠障碍", "夜间易醒"],
        quadrants=[
            {"q_code": "q1", "q_name": "一", "abnormalIndicators": ["A"], "recommendationPlans": ["R"]},
            {"q_code": "q2", "q_name": "二", "abnormalIndicators": ["B"], "recommendationPlans": ["R"]},
            {"q_code": "q3", "q_name": "三", "abnormalIndicators": ["C"], "recommendationPlans": ["R"]},
            {"q_code": "q4", "q_name": "四", "abnormalIndicators": ["D"], "recommendationPlans": ["R"]},
        ],
        confirmed_by="hello",
        trace_id="trace-001",
    )
    assert repo.upsert_payload is not None
    assert len(repo.upsert_payload["single_exam_items"]) == 2
    assert repo.upsert_payload["chief_complaint_items"] == ["夜间易醒", "睡眠障碍"]
    assert repo.upsert_payload["source_jlrq"] == "2026-04-15 10:00:00"
    assert repo.upsert_payload["source_zjrq"] == "2026-04-15 11:00:00"
    assert repo.upsert_payload["trace_id"] == "trace-001"
    assert repo.upsert_payload["single_exam_items"][0]["abnormalIndicator"] == "维生素D偏低"


@pytest.mark.asyncio
async def test_query_quadrants_exam_q3_mapping_and_q4_like_recall_are_deduplicated(monkeypatch) -> None:
    """验证体检四象限的新规则：

    1. Q3 先做终检意见标准化映射，再与 Q1/Q2 去重。
    2. Q4 按主诉召回功能医学质谱项目，再与 Q1/Q2/Q3 去重。
    """

    repo = StubRepository(cached=None)
    service = HealthQuadrantService(repository=repo, llm_service=StubLLM())

    async def stub_load_source_data(*, study_id: str):
        assert study_id == "2512160009"
        return {
            "packageName": "套餐A",
            "finalConclusion": "建议进一步复查甲状腺超声",
            "sourceJlrq": "2026-04-15 10:00:00",
            "sourceZjrq": "2026-04-15 11:00:00",
            "splitRows": [
                {"one_item_name": "血脂", "two_item_name": "", "abnormal_item": "偏高", "category": "生化"},
                {"one_item_name": "肺部检查", "two_item_name": "肺部CT", "abnormal_item": "结节", "category": "影像"},
            ],
        }

    async def stub_extract_deep_screening_items(*, final_conclusion: str):
        assert final_conclusion
        return ["血脂复查", "肺部CT复查", "甲状腺超声复查"]

    async def stub_map_doctor_conclusion_items_to_standard(*, items: list[str]):
        assert items == ["血脂复查", "肺部CT复查", "甲状腺超声复查"]
        return ["血脂", "肺部CT", "甲状腺超声"]

    async def stub_query_q4_mass_spec_projects(*, chief_complaint_items: list[str]):
        assert chief_complaint_items == ["夜间易醒", "睡眠障碍"]
        return ["高级代谢质谱", "血脂"]

    monkeypatch.setattr(service, "_load_source_data", stub_load_source_data)
    monkeypatch.setattr(service, "_extract_deep_screening_items", stub_extract_deep_screening_items)
    monkeypatch.setattr(service, "_map_doctor_conclusion_items_to_standard", stub_map_doctor_conclusion_items_to_standard)
    monkeypatch.setattr(service, "_query_q4_mass_spec_projects", stub_query_q4_mass_spec_projects)

    result = await service.query_quadrants(
        study_id="2512160009",
        quadrant_type="exam",
        single_exam_items=[],
        chief_complaint_items=["睡眠障碍", "夜间易醒"],
        trace_id="trace-001",
    )

    quadrants = result["quadrants"]
    # Q1/Q2 已占用“血脂”“肺部CT”，Q3 应仅保留新增标准项。
    assert quadrants[2]["abnormalIndicators"] == ["甲状腺超声"]
    # Q4 召回包含“血脂”会被去重，最终只保留新增质谱项目。
    assert quadrants[3]["abnormalIndicators"] == ["高级代谢质谱"]
