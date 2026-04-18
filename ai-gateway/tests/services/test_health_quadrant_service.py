from __future__ import annotations

import pytest

from app.services.health_quadrant_service import (
    HealthQuadrantService,
    HealthQuadrantServiceError,
    _TreatmentTriageItem,
)


class StubTreatmentRepository:
    def __init__(self, rows: list[dict] | None = None):
        self.rows = rows or []
        self.called = False

    async def match_candidates(self, *, triage_items):
        self.called = True
        return self.rows

    async def close(self) -> None:
        return None


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
        chief_complaint_text: str | None,
        source_jlrq=None,
        source_zjrq=None,
        draft_not_older_than,
        trace_id: str | None = None,
    ) -> tuple[dict | None, str | None]:
        assert study_id == "2512160009"
        assert quadrant_type in {"exam", "treatment"}
        # 该仓储桩复用于多条测试场景，不强绑单项数量，避免测试之间互相耦合。
        assert isinstance(single_exam_items, list)
        assert chief_complaint_text == (chief_complaint_text.strip() if chief_complaint_text else chief_complaint_text)
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
    def __init__(self, responses: list[str] | None = None):
        self.responses = list(responses or ['{"items":["建议复查甲状腺超声"]}'])
        self.calls = 0

    async def chat(self, *args, **kwargs) -> str:
        idx = min(self.calls, len(self.responses) - 1)
        self.calls += 1
        return self.responses[idx]


def test_treatment_triage_item_dedupe_key_prefers_value_or_desc_when_prefix_matches_item_name() -> None:
    item = _TreatmentTriageItem(
        item_name="血压",
        value_or_desc="血压偏高(150/95)",
        quadrant="ORANGE",
        belong_system="心脑血管",
        reason="",
    )
    assert item.dedupe_key == "血压偏高(150/95)"


def test_treatment_triage_item_dedupe_key_keeps_item_name_when_prefix_not_match() -> None:
    item = _TreatmentTriageItem(
        item_name="血压",
        value_or_desc="收缩压偏高",
        quadrant="ORANGE",
        belong_system="心脑血管",
        reason="",
    )
    assert item.dedupe_key == "血压 + 收缩压偏高"


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

    async def stub_load_source_data(*, study_id: str, trace_id: str | None = None):
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
        sex="男",
        age=None,
        study_id="2512160009",
        quadrant_type="exam",
        single_exam_items=[
            {"itemId": "A1", "itemText": "维生素D缺乏", "abnormalIndicator": "维生素D偏低"},
            {"itemId": "A2", "itemText": "甲状腺结节", "abnormalIndicator": "结节"},
        ],
        chief_complaint_text="睡眠障碍，夜间易醒",
        trace_id="trace-001",
    )
    assert result["fromCache"] is True
    assert len(result["quadrants"]) == 4
    assert repo.draft_payload is None


@pytest.mark.asyncio
async def test_query_quadrants_exam_uses_one_two_item_split(monkeypatch) -> None:
    repo = StubRepository(cached=None)
    treatment_repo = StubTreatmentRepository()
    service = HealthQuadrantService(repository=repo, llm_service=StubLLM(), treatment_repository=treatment_repo)

    async def stub_load_source_data(*, study_id: str, trace_id: str | None = None):
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

    async def stub_extract_deep_screening_items(*, final_conclusion: str, trace_id: str | None = None, study_id: str | None = None):
        assert final_conclusion
        return ["甲状腺超声复查"]

    monkeypatch.setattr(service, "_load_source_data", stub_load_source_data)
    monkeypatch.setattr(service, "_extract_deep_screening_items", stub_extract_deep_screening_items)
    result = await service.query_quadrants(
        sex="男",
        age=None,
        study_id="2512160009",
        quadrant_type="exam",
        single_exam_items=[
            {"itemId": "A1", "itemText": "维生素", "abnormalIndicator": "维生素D偏低"},
            {"itemId": "A2", "itemText": "甲状腺超声", "abnormalIndicator": "结节"},
        ],
        chief_complaint_text="睡眠障碍，夜间易醒",
        trace_id="trace-001",
    )
    assert result["fromCache"] is False
    quadrants = result["quadrants"]
    assert len(quadrants) == 4
    assert "偏高" in quadrants[0]["abnormalIndicators"]
    assert "结节" in quadrants[1]["abnormalIndicators"]
    assert "血脂" in quadrants[0]["recommendationPlans"]
    assert "肺部CT" in quadrants[1]["recommendationPlans"]
    assert "维生素" in quadrants[2]["recommendationPlans"]
    assert "维生素D偏低" in quadrants[2]["abnormalIndicators"]
    assert repo.draft_payload is not None
    assert repo.draft_payload["quadrant_type"] == "exam"
    assert repo.draft_payload["source_jlrq"] == "2026-04-15 10:00:00"
    assert repo.draft_payload["source_zjrq"] == "2026-04-15 11:00:00"


@pytest.mark.asyncio
async def test_confirm_quadrants_persists_with_multi_items() -> None:
    repo = StubRepository(cached=None)
    service = HealthQuadrantService(repository=repo, llm_service=StubLLM())
    async def stub_load_source_data(*, study_id: str, trace_id: str | None = None):
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
        chief_complaint_text="睡眠障碍，夜间易醒",
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
    assert repo.upsert_payload["chief_complaint_text"] == "睡眠障碍，夜间易醒"
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

    async def stub_load_source_data(*, study_id: str, trace_id: str | None = None):
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

    async def stub_extract_deep_screening_items(*, final_conclusion: str, trace_id: str | None = None, study_id: str | None = None):
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
        sex="男",
        age=None,
        study_id="2512160009",
        quadrant_type="exam",
        single_exam_items=[],
        chief_complaint_text="睡眠障碍，夜间易醒",
        trace_id="trace-001",
    )

    quadrants = result["quadrants"]
    # Q1/Q2 已占用“血脂”“肺部CT”，Q3 应仅保留新增标准项。
    assert quadrants[2]["recommendationPlans"] == ["甲状腺超声"]
    # Q4 召回包含“血脂”会被去重，最终只保留新增质谱项目。
    assert quadrants[3]["recommendationPlans"] == ["高级代谢质谱", "全基因检测", "PET-MR 高端筛查评估"]


@pytest.mark.asyncio
async def test_query_quadrants_treatment_three_stage_success(monkeypatch) -> None:
    repo = StubRepository(cached=None)
    treatment_repo = StubTreatmentRepository(
        rows=[
            {
                "project_name": "冠脉风险高级评估",
                "package_version": "v1",
                "contraindications": "",
                "quadrant": "RED",
                "belong_system": "心脑血管",
                "trigger_item": "胸闷",
                "match_source": "indicator_name",
            },
            {
                "project_name": "代谢专项管理",
                "package_version": "v2",
                "contraindications": "",
                "quadrant": "ORANGE",
                "belong_system": "内分泌系统",
                "trigger_item": "血糖升高",
                "match_source": "indicator_name",
            },
        ]
    )
    llm = StubLLM(
        responses=[
            """{
              "triage_results":[
                {"item_name":"胸闷","value_or_desc":"胸闷持续","quadrant":"RED","belong_system":"心脑血管","reason":"高风险"},
                {"item_name":"血糖","value_or_desc":"血糖升高","quadrant":"ORANGE","belong_system":"内分泌系统","reason":"需干预"}
              ]
            }""",
            """{
              "safety_checks":[
                {"candidate_id":"冠脉风险高级评估||v1||RED","project_name":"冠脉风险高级评估","reason":"无明显禁忌","is_contraindicated":false}
              ]
            }""",
            """{
              "safety_checks":[
                {"candidate_id":"代谢专项管理||v2||ORANGE","project_name":"代谢专项管理","reason":"存在禁忌","is_contraindicated":true}
              ]
            }""",
        ]
    )
    service = HealthQuadrantService(repository=repo, llm_service=llm, treatment_repository=treatment_repo)

    async def stub_load_source_data(*, study_id: str, trace_id: str | None = None):
        assert study_id == "2512160009"
        return {
            "packageName": "套餐A",
            "finalConclusion": "存在胸闷风险",
            "sourceJlrq": "2026-04-15 10:00:00",
            "sourceZjrq": "2026-04-15 11:00:00",
            "splitRows": [{"abnormal_item": "胸闷持续"}],
            "jcjg": "胸闷持续",
        }

    monkeypatch.setattr(service, "_load_source_data", stub_load_source_data)
    result = await service.query_quadrants(
        sex="男",
        age=None,
        study_id="2512160009",
        quadrant_type="treatment",
        single_exam_items=[{"itemId": "A1", "itemText": "血糖", "abnormalIndicator": "血糖升高"}],
        chief_complaint_text="胸闷",
        trace_id="trace-001",
    )
    assert result["fromCache"] is False
    quadrants = result["quadrants"]
    assert quadrants[0]["recommendationPlans"] == ["冠脉风险高级评估 (v1)"]
    assert quadrants[1]["recommendationPlans"] == []
    assert repo.draft_payload is not None


@pytest.mark.asyncio
async def test_query_quadrants_treatment_triage_top_level_failure(monkeypatch) -> None:
    repo = StubRepository(cached=None)
    treatment_repo = StubTreatmentRepository(rows=[])
    llm = StubLLM(responses=["not json"])
    service = HealthQuadrantService(repository=repo, llm_service=llm, treatment_repository=treatment_repo)

    async def stub_load_source_data(*, study_id: str, trace_id: str | None = None):
        return {
            "packageName": "",
            "finalConclusion": "异常",
            "sourceJlrq": "2026-04-15 10:00:00",
            "sourceZjrq": "2026-04-15 11:00:00",
            "splitRows": [{"abnormal_item": "胸闷持续"}],
            "jcjg": "胸闷持续",
        }

    monkeypatch.setattr(service, "_load_source_data", stub_load_source_data)
    with pytest.raises(HealthQuadrantServiceError, match="triage_failed"):
        await service.query_quadrants(
            sex="男",
            age=None,
            study_id="2512160009",
            quadrant_type="treatment",
            single_exam_items=[],
            chief_complaint_text="胸闷",
            trace_id="trace-001",
        )


@pytest.mark.asyncio
async def test_query_quadrants_treatment_safety_top_level_failure(monkeypatch) -> None:
    repo = StubRepository(cached=None)
    treatment_repo = StubTreatmentRepository(
        rows=[
            {
                "project_name": "冠脉风险高级评估",
                "package_version": "v1",
                "contraindications": "",
                "quadrant": "RED",
                "belong_system": "心脑血管",
                "trigger_item": "胸闷",
                "match_source": "indicator_name",
            }
        ]
    )
    llm = StubLLM(
        responses=[
            """{
              "triage_results":[
                {"item_name":"胸闷","value_or_desc":"胸闷持续","quadrant":"RED","belong_system":"心脑血管","reason":"高风险"}
              ]
            }""",
            "not json",
        ]
    )
    service = HealthQuadrantService(repository=repo, llm_service=llm, treatment_repository=treatment_repo)

    async def stub_load_source_data(*, study_id: str, trace_id: str | None = None):
        return {
            "packageName": "",
            "finalConclusion": "异常",
            "sourceJlrq": "2026-04-15 10:00:00",
            "sourceZjrq": "2026-04-15 11:00:00",
            "splitRows": [{"abnormal_item": "胸闷持续"}],
            "jcjg": "胸闷持续",
        }

    monkeypatch.setattr(service, "_load_source_data", stub_load_source_data)
    with pytest.raises(HealthQuadrantServiceError, match="safety_failed"):
        await service.query_quadrants(
            sex="男",
            age=None,
            study_id="2512160009",
            quadrant_type="treatment",
            single_exam_items=[],
            chief_complaint_text="胸闷",
            trace_id="trace-001",
        )


@pytest.mark.asyncio
async def test_query_quadrants_treatment_row_level_drop_and_empty_after_safety(monkeypatch) -> None:
    repo = StubRepository(cached=None)
    treatment_repo = StubTreatmentRepository(
        rows=[
            {
                "project_name": "冠脉风险高级评估",
                "package_version": "v1",
                "contraindications": "",
                "quadrant": "RED",
                "belong_system": "心脑血管",
                "trigger_item": "胸闷",
                "match_source": "indicator_name",
            }
        ]
    )
    llm = StubLLM(
        responses=[
            """{
              "triage_results":[
                {"item_name":"胸闷","value_or_desc":"胸闷持续","quadrant":"RED","belong_system":"心脑血管","reason":"高风险"},
                {"item_name":"坏数据","value_or_desc":"","quadrant":"BLUE","belong_system":"未知系统","reason":"无效"}
              ]
            }""",
            """{
              "safety_checks":[
                {"candidate_id":"冠脉风险高级评估||v1||RED","project_name":"冠脉风险高级评估","reason":"禁忌","is_contraindicated":true},
                {"candidate_id":"","project_name":"坏数据","reason":"无效","is_contraindicated":"no"}
              ]
            }""",
        ]
    )
    service = HealthQuadrantService(repository=repo, llm_service=llm, treatment_repository=treatment_repo)

    async def stub_load_source_data(*, study_id: str, trace_id: str | None = None):
        return {
            "packageName": "",
            "finalConclusion": "异常",
            "sourceJlrq": "2026-04-15 10:00:00",
            "sourceZjrq": "2026-04-15 11:00:00",
            "splitRows": [{"abnormal_item": "胸闷持续"}],
            "jcjg": "胸闷持续",
        }

    monkeypatch.setattr(service, "_load_source_data", stub_load_source_data)
    result = await service.query_quadrants(
        sex="男",
        age=None,
        study_id="2512160009",
        quadrant_type="treatment",
        single_exam_items=[],
        chief_complaint_text="胸闷",
        trace_id="trace-001",
    )
    quadrants = result["quadrants"]
    assert quadrants[0]["recommendationPlans"] == []
    assert quadrants[3]["abnormalIndicators"] == ["无安全可推荐项目"]


@pytest.mark.asyncio
async def test_query_quadrants_treatment_safety_limit_top3_per_quadrant(monkeypatch) -> None:
    repo = StubRepository(cached=None)
    treatment_repo = StubTreatmentRepository(
        rows=[
            {
                "project_name": "红区项目A",
                "package_version": "v1",
                "contraindications": "",
                "quadrant": "RED",
                "belong_system": "心脑血管",
                "trigger_item": "胸闷",
                "match_source": "indicator_name",
            },
            {
                "project_name": "红区项目B",
                "package_version": "v1",
                "contraindications": "",
                "quadrant": "RED",
                "belong_system": "心脑血管",
                "trigger_item": "胸闷",
                "match_source": "indicator_name",
            },
            {
                "project_name": "红区项目C",
                "package_version": "v1",
                "contraindications": "",
                "quadrant": "RED",
                "belong_system": "心脑血管",
                "trigger_item": "胸闷",
                "match_source": "indicator_name",
            },
            {
                "project_name": "红区项目D",
                "package_version": "v1",
                "contraindications": "",
                "quadrant": "RED",
                "belong_system": "心脑血管",
                "trigger_item": "胸闷",
                "match_source": "indicator_name",
            },
        ]
    )
    llm = StubLLM(
        responses=[
            """{
              "triage_results":[
                {"item_name":"胸闷","value_or_desc":"胸闷持续","quadrant":"RED","belong_system":"心脑血管","reason":"高风险"}
              ]
            }""",
            """{
              "safety_checks":[
                {"candidate_id":"红区项目A||v1||RED","project_name":"红区项目A","reason":"可用","is_contraindicated":false},
                {"candidate_id":"红区项目B||v1||RED","project_name":"红区项目B","reason":"可用","is_contraindicated":false},
                {"candidate_id":"红区项目C||v1||RED","project_name":"红区项目C","reason":"可用","is_contraindicated":false},
                {"candidate_id":"红区项目D||v1||RED","project_name":"红区项目D","reason":"可用","is_contraindicated":false}
              ]
            }""",
        ]
    )
    service = HealthQuadrantService(repository=repo, llm_service=llm, treatment_repository=treatment_repo)

    async def stub_load_source_data(*, study_id: str, trace_id: str | None = None):
        return {
            "packageName": "",
            "finalConclusion": "异常",
            "sourceJlrq": "2026-04-15 10:00:00",
            "sourceZjrq": "2026-04-15 11:00:00",
            "splitRows": [{"abnormal_item": "胸闷持续"}],
            "jcjg": "胸闷持续",
        }

    monkeypatch.setattr(service, "_load_source_data", stub_load_source_data)
    result = await service.query_quadrants(
        sex="男",
        age=None,
        study_id="2512160009",
        quadrant_type="treatment",
        single_exam_items=[],
        chief_complaint_text="胸闷",
        trace_id="trace-001",
    )
    quadrants = result["quadrants"]
    assert quadrants[0]["recommendationPlans"] == [
        "红区项目A (v1)",
        "红区项目B (v1)",
        "红区项目C (v1)",
    ]


@pytest.mark.asyncio
async def test_query_quadrants_treatment_triage_accepts_nested_items_key(monkeypatch) -> None:
    repo = StubRepository(cached=None)
    treatment_repo = StubTreatmentRepository(
        rows=[
            {
                "project_name": "冠脉风险高级评估",
                "package_version": "v1",
                "contraindications": "",
                "quadrant": "RED",
                "belong_system": "心脑血管",
                "trigger_item": "胸闷",
                "match_source": "indicator_name",
            }
        ]
    )
    llm = StubLLM(
        responses=[
            """{
              "data":{
                "items":[
                  {"item_name":"胸闷","value_or_desc":"胸闷持续","quadrant":"RED","belong_system":"心脑血管","reason":"高风险"}
                ]
              }
            }""",
            """{
              "safety_checks":[
                {"project_name":"冠脉风险高级评估","reason":"无明显禁忌","is_contraindicated":false}
              ]
            }""",
        ]
    )
    service = HealthQuadrantService(repository=repo, llm_service=llm, treatment_repository=treatment_repo)

    async def stub_load_source_data(*, study_id: str, trace_id: str | None = None):
        return {
            "packageName": "",
            "finalConclusion": "异常",
            "sourceJlrq": "2026-04-15 10:00:00",
            "sourceZjrq": "2026-04-15 11:00:00",
            "splitRows": [{"abnormal_item": "胸闷持续"}],
            "jcjg": "胸闷持续",
        }

    monkeypatch.setattr(service, "_load_source_data", stub_load_source_data)
    result = await service.query_quadrants(
        sex="男",
        age=65,
        study_id="2512160009",
        quadrant_type="treatment",
        single_exam_items=[],
        chief_complaint_text="睡眠障碍, 夜间易醒",
        trace_id="trace-001",
    )

    assert result["quadrants"][0]["recommendationPlans"] == ["冠脉风险高级评估 (v1)"]


@pytest.mark.asyncio
async def test_query_quadrants_treatment_safety_uses_quadrant_specific_abnormal_text(monkeypatch) -> None:
    repo = StubRepository(cached=None)
    treatment_repo = StubTreatmentRepository(
        rows=[
            {
                "project_name": "红区项目A",
                "package_version": "v1",
                "contraindications": "",
                "quadrant": "RED",
                "belong_system": "心脑血管",
                "trigger_item": "胸闷",
                "match_source": "indicator_name",
            },
            {
                "project_name": "橙区项目A",
                "package_version": "v1",
                "contraindications": "",
                "quadrant": "ORANGE",
                "belong_system": "内分泌系统",
                "trigger_item": "血糖",
                "match_source": "indicator_name",
            },
        ]
    )

    class RecordingStubLLM(StubLLM):
        def __init__(self, responses: list[str] | None = None):
            super().__init__(responses=responses)
            self.prompts: list[str] = []

        async def chat(self, *args, **kwargs) -> str:
            messages = args[0] if args else kwargs.get("messages", [])
            if isinstance(messages, list) and messages and isinstance(messages[0], dict):
                self.prompts.append(str(messages[0].get("content", "")))
            return await super().chat(*args, **kwargs)

    llm = RecordingStubLLM(
        responses=[
            """{
              "triage_results":[
                {"item_name":"胸闷","value_or_desc":"胸闷持续","quadrant":"RED","belong_system":"心脑血管","reason":"高风险"},
                {"item_name":"血糖","value_or_desc":"血糖升高","quadrant":"ORANGE","belong_system":"内分泌系统","reason":"需干预"}
              ]
            }""",
            """{
              "safety_checks":[
                {"candidate_id":"红区项目A||v1||RED","project_name":"红区项目A","reason":"可用","is_contraindicated":false}
              ]
            }""",
            """{
              "safety_checks":[
                {"candidate_id":"橙区项目A||v1||ORANGE","project_name":"橙区项目A","reason":"可用","is_contraindicated":false}
              ]
            }""",
        ]
    )
    service = HealthQuadrantService(repository=repo, llm_service=llm, treatment_repository=treatment_repo)

    async def stub_load_source_data(*, study_id: str, trace_id: str | None = None):
        return {
            "packageName": "",
            "finalConclusion": "异常",
            "sourceJlrq": "2026-04-15 10:00:00",
            "sourceZjrq": "2026-04-15 11:00:00",
            "splitRows": [{"abnormal_item": "胸闷持续"}],
            "jcjg": "胸闷持续",
        }

    monkeypatch.setattr(service, "_load_source_data", stub_load_source_data)
    result = await service.query_quadrants(
        sex="男",
        age=65,
        study_id="2512160009",
        quadrant_type="treatment",
        single_exam_items=[{"itemId": "A1", "itemText": "血糖", "abnormalIndicator": "血糖升高"}],
        chief_complaint_text="睡眠障碍, 夜间易醒",
        trace_id="trace-001",
    )

    assert result["quadrants"][0]["recommendationPlans"] == ["红区项目A (v1)"]
    assert result["quadrants"][1]["recommendationPlans"] == ["橙区项目A (v1)"]

    # 第 1 次为 triage，后续为并发 safety 请求；验证每个 safety prompt 仅包含本象限异常文本。
    safety_prompts = llm.prompts[1:]
    assert any("胸闷持续" in prompt and "血糖升高" not in prompt for prompt in safety_prompts)
    assert any("血糖升高" in prompt and "胸闷持续" not in prompt for prompt in safety_prompts)
