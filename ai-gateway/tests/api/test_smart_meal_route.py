from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import dependencies as api_dependencies
from app.api.routes import smart_meal as smart_meal_route
from app.core.error_codes import BusinessError, ErrorCode
from app.services.smart_meal_risk_service import SmartMealRiskService
from app.services.smart_meal_risk_service import SmartMealRiskServiceError


class StubSmartMealRiskService:
    async def identify_risks(
        self,
        *,
        id_card_no: str,
        campus_id: str,
        meal_snapshot: list[dict[str, str | None]],
        trace_id: str | None,
    ) -> list[dict[str, object]]:
        assert id_card_no == "110101199001011234"
        assert campus_id == "TJ-001"
        assert meal_snapshot == [
            {"dish_code": "DISH-001", "dish_name": "蒜蓉西兰花"},
            {"dish_code": None, "dish_name": "会被跳过"},
            {"dish_code": "DISH-002", "dish_name": "清炒时蔬"},
        ]
        assert trace_id == "trace-001"
        return [
            {
                "ingredient": "西兰花",
                "intolerance_level": "2级",
                "dishes": [
                    {"dish_code": "DISH-001", "dish_name": "蒜蓉西兰花"},
                    {"dish_code": "DISH-002", "dish_name": "清炒时蔬"},
                ],
            }
        ]


def create_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(smart_meal_route.router, prefix="/api/v1")
    return app


def test_smart_meal_route_returns_envelope(monkeypatch) -> None:
    app = create_test_app()
    app.dependency_overrides[api_dependencies.get_smart_meal_risk_service] = lambda: StubSmartMealRiskService()
    client = TestClient(app)

    response = client.post(
        "/api/v1/smart-meal/risk-identify",
        headers={"X-Trace-Id": "trace-001"},
        json={
            "id_card_no": "110101199001011234",
            "campusId": "TJ-001",
            "mealSnapshot": [
                {"dishCode": "DISH-001", "dishName": "蒜蓉西兰花"},
                {"dishCode": None, "dishName": "会被跳过"},
                {"dishCode": "DISH-002", "dishName": "清炒时蔬"},
            ],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 0
    assert payload["message"] == "ok"
    assert payload["data"] == [
        {
            "ingredient": "西兰花",
            "intolerance_level": "2级",
            "dishes": [
                {"dishCode": "DISH-001", "dishName": "蒜蓉西兰花"},
                {"dishCode": "DISH-002", "dishName": "清炒时蔬"},
            ],
        }
    ]
    app.dependency_overrides.pop(api_dependencies.get_smart_meal_risk_service, None)


def test_smart_meal_route_rejects_legacy_snake_case_fields(monkeypatch) -> None:
    app = create_test_app()
    app.dependency_overrides[api_dependencies.get_smart_meal_risk_service] = lambda: StubSmartMealRiskService()
    client = TestClient(app)

    response = client.post(
        "/api/v1/smart-meal/risk-identify",
        headers={"X-Trace-Id": "trace-001"},
        json={
            "id_card_no": "110101199001011234",
            "campus_id": "TJ-001",
            "meal_snapshot": [{"dish_code": "DISH-001", "dish_name": "蒜蓉西兰花"}],
        },
    )
    assert response.status_code == 422
    app.dependency_overrides.pop(api_dependencies.get_smart_meal_risk_service, None)


def test_smart_meal_route_rejects_camel_id_card_no(monkeypatch) -> None:
    app = create_test_app()
    app.dependency_overrides[api_dependencies.get_smart_meal_risk_service] = lambda: StubSmartMealRiskService()
    client = TestClient(app)

    response = client.post(
        "/api/v1/smart-meal/risk-identify",
        headers={"X-Trace-Id": "trace-001"},
        json={
            "idCardNo": "110101199001011234",
            "campusId": "TJ-001",
            "mealSnapshot": [{"dishCode": "DISH-001", "dishName": "蒜蓉西兰花"}],
        },
    )
    assert response.status_code == 422
    app.dependency_overrides.pop(api_dependencies.get_smart_meal_risk_service, None)


def test_smart_meal_route_rejects_legacy_snake_case_dish_fields_in_meal_snapshot(monkeypatch) -> None:
    app = create_test_app()
    app.dependency_overrides[api_dependencies.get_smart_meal_risk_service] = lambda: StubSmartMealRiskService()
    client = TestClient(app)

    response = client.post(
        "/api/v1/smart-meal/risk-identify",
        headers={"X-Trace-Id": "trace-001"},
        json={
            "id_card_no": "110101199001011234",
            "campusId": "TJ-001",
            "mealSnapshot": [{"dish_code": "DISH-001", "dish_name": "蒜蓉西兰花"}],
        },
    )
    assert response.status_code == 422
    detail = response.json().get("detail", [])
    assert any(
        item.get("type") == "extra_forbidden" and item.get("loc") == ["body", "mealSnapshot", 0, "dish_code"]
        for item in detail
    )
    assert any(
        item.get("type") == "extra_forbidden" and item.get("loc") == ["body", "mealSnapshot", 0, "dish_name"]
        for item in detail
    )
    app.dependency_overrides.pop(api_dependencies.get_smart_meal_risk_service, None)


def test_smart_meal_route_rejects_mixed_alias_and_legacy_dish_fields(monkeypatch) -> None:
    app = create_test_app()
    app.dependency_overrides[api_dependencies.get_smart_meal_risk_service] = lambda: StubSmartMealRiskService()
    client = TestClient(app)

    response = client.post(
        "/api/v1/smart-meal/risk-identify",
        headers={"X-Trace-Id": "trace-001"},
        json={
            "id_card_no": "110101199001011234",
            "campusId": "TJ-001",
            "mealSnapshot": [
                {"dishCode": "DISH-001", "dishName": "蒜蓉西兰花", "dish_code": "DISH-001"},
            ],
        },
    )
    assert response.status_code == 422
    detail = response.json().get("detail", [])
    assert any(
        item.get("type") == "extra_forbidden" and item.get("loc") == ["body", "mealSnapshot", 0, "dish_code"]
        for item in detail
    )
    app.dependency_overrides.pop(api_dependencies.get_smart_meal_risk_service, None)


def test_smart_meal_route_rejects_mixed_alias_and_legacy_dish_name_field(monkeypatch) -> None:
    app = create_test_app()
    app.dependency_overrides[api_dependencies.get_smart_meal_risk_service] = lambda: StubSmartMealRiskService()
    client = TestClient(app)

    response = client.post(
        "/api/v1/smart-meal/risk-identify",
        headers={"X-Trace-Id": "trace-001"},
        json={
            "id_card_no": "110101199001011234",
            "campusId": "TJ-001",
            "mealSnapshot": [
                {"dishCode": "DISH-001", "dishName": "蒜蓉西兰花", "dish_name": "蒜蓉西兰花"},
            ],
        },
    )
    assert response.status_code == 422
    detail = response.json().get("detail", [])
    assert any(
        item.get("type") == "extra_forbidden" and item.get("loc") == ["body", "mealSnapshot", 0, "dish_name"]
        for item in detail
    )
    app.dependency_overrides.pop(api_dependencies.get_smart_meal_risk_service, None)


def test_smart_meal_route_rejects_mixed_top_level_campus_fields(monkeypatch) -> None:
    app = create_test_app()
    app.dependency_overrides[api_dependencies.get_smart_meal_risk_service] = lambda: StubSmartMealRiskService()
    client = TestClient(app)

    response = client.post(
        "/api/v1/smart-meal/risk-identify",
        headers={"X-Trace-Id": "trace-001"},
        json={
            "id_card_no": "110101199001011234",
            "campusId": "TJ-001",
            "campus_id": "TJ-001",
            "mealSnapshot": [{"dishCode": "DISH-001", "dishName": "蒜蓉西兰花"}],
        },
    )
    assert response.status_code == 422
    detail = response.json().get("detail", [])
    assert any(item.get("type") == "extra_forbidden" and item.get("loc") == ["body", "campus_id"] for item in detail)
    app.dependency_overrides.pop(api_dependencies.get_smart_meal_risk_service, None)


def test_smart_meal_route_rejects_mixed_top_level_id_card_fields(monkeypatch) -> None:
    app = create_test_app()
    app.dependency_overrides[api_dependencies.get_smart_meal_risk_service] = lambda: StubSmartMealRiskService()
    client = TestClient(app)

    response = client.post(
        "/api/v1/smart-meal/risk-identify",
        headers={"X-Trace-Id": "trace-001"},
        json={
            "id_card_no": "110101199001011234",
            "idCardNo": "110101199001011234",
            "campusId": "TJ-001",
            "mealSnapshot": [{"dishCode": "DISH-001", "dishName": "蒜蓉西兰花"}],
        },
    )
    assert response.status_code == 422
    detail = response.json().get("detail", [])
    assert any(item.get("type") == "extra_forbidden" and item.get("loc") == ["body", "idCardNo"] for item in detail)
    app.dependency_overrides.pop(api_dependencies.get_smart_meal_risk_service, None)


def test_smart_meal_route_rejects_mixed_top_level_meal_snapshot_fields(monkeypatch) -> None:
    app = create_test_app()
    app.dependency_overrides[api_dependencies.get_smart_meal_risk_service] = lambda: StubSmartMealRiskService()
    client = TestClient(app)

    response = client.post(
        "/api/v1/smart-meal/risk-identify",
        headers={"X-Trace-Id": "trace-001"},
        json={
            "id_card_no": "110101199001011234",
            "campusId": "TJ-001",
            "mealSnapshot": [{"dishCode": "DISH-001", "dishName": "蒜蓉西兰花"}],
            "meal_snapshot": [{"dish_code": "DISH-001", "dish_name": "蒜蓉西兰花"}],
        },
    )
    assert response.status_code == 422
    detail = response.json().get("detail", [])
    assert any(item.get("type") == "extra_forbidden" and item.get("loc") == ["body", "meal_snapshot"] for item in detail)
    app.dependency_overrides.pop(api_dependencies.get_smart_meal_risk_service, None)


def test_smart_meal_route_rejects_unknown_nested_meal_snapshot_field(monkeypatch) -> None:
    app = create_test_app()
    app.dependency_overrides[api_dependencies.get_smart_meal_risk_service] = lambda: StubSmartMealRiskService()
    client = TestClient(app)

    response = client.post(
        "/api/v1/smart-meal/risk-identify",
        headers={"X-Trace-Id": "trace-001"},
        json={
            "id_card_no": "110101199001011234",
            "campusId": "TJ-001",
            "mealSnapshot": [{"dishCode": "DISH-001", "dishName": "蒜蓉西兰花", "foo": "bar"}],
        },
    )
    assert response.status_code == 422
    detail = response.json().get("detail", [])
    assert any(item.get("type") == "extra_forbidden" and item.get("loc") == ["body", "mealSnapshot", 0, "foo"] for item in detail)
    app.dependency_overrides.pop(api_dependencies.get_smart_meal_risk_service, None)


def test_smart_meal_route_rejects_unknown_top_level_field(monkeypatch) -> None:
    app = create_test_app()
    app.dependency_overrides[api_dependencies.get_smart_meal_risk_service] = lambda: StubSmartMealRiskService()
    client = TestClient(app)

    response = client.post(
        "/api/v1/smart-meal/risk-identify",
        headers={"X-Trace-Id": "trace-001"},
        json={
            "id_card_no": "110101199001011234",
            "campusId": "TJ-001",
            "mealSnapshot": [{"dishCode": "DISH-001", "dishName": "蒜蓉西兰花"}],
            "foo": "bar",
        },
    )
    assert response.status_code == 422
    detail = response.json().get("detail", [])
    assert any(item.get("type") == "extra_forbidden" and item.get("loc") == ["body", "foo"] for item in detail)
    app.dependency_overrides.pop(api_dependencies.get_smart_meal_risk_service, None)


def test_smart_meal_route_rejects_empty_meal_snapshot_list(monkeypatch) -> None:
    app = create_test_app()
    app.dependency_overrides[api_dependencies.get_smart_meal_risk_service] = lambda: StubSmartMealRiskService()
    client = TestClient(app)

    response = client.post(
        "/api/v1/smart-meal/risk-identify",
        headers={"X-Trace-Id": "trace-001"},
        json={
            "id_card_no": "110101199001011234",
            "campusId": "TJ-001",
            "mealSnapshot": [],
        },
    )
    assert response.status_code == 422
    app.dependency_overrides.pop(api_dependencies.get_smart_meal_risk_service, None)


def test_smart_meal_route_maps_real_service_blank_id_card_no_to_external_error(monkeypatch) -> None:
    app = create_test_app()
    app.dependency_overrides[api_dependencies.get_smart_meal_risk_service] = lambda: SmartMealRiskService()
    client = TestClient(app)

    with pytest.raises(BusinessError) as exc_info:
        client.post(
            "/api/v1/smart-meal/risk-identify",
            headers={"X-Trace-Id": "trace-001"},
            json={
                "id_card_no": "   ",
                "campusId": "TJ-001",
                "mealSnapshot": [{"dishCode": "DISH-001", "dishName": "蒜蓉西兰花"}],
            },
        )
    assert exc_info.value.error_code == ErrorCode.EXTERNAL_SERVICE_ERROR
    assert "食物不耐受接口调用失败" in exc_info.value.detail
    app.dependency_overrides.pop(api_dependencies.get_smart_meal_risk_service, None)


def test_smart_meal_route_maps_service_bad_request_to_400(monkeypatch) -> None:
    class BadRequestSmartMealRiskService:
        async def identify_risks(self, **kwargs):  # noqa: ANN003, ANN201
            raise SmartMealRiskServiceError("bad_request: meal_snapshot 不能为空")

    app = create_test_app()
    app.dependency_overrides[api_dependencies.get_smart_meal_risk_service] = lambda: BadRequestSmartMealRiskService()
    client = TestClient(app)

    with pytest.raises(BusinessError) as exc_info:
        client.post(
            "/api/v1/smart-meal/risk-identify",
            headers={"X-Trace-Id": "trace-001"},
            json={
                "id_card_no": "110101199001011234",
                "campusId": "TJ-001",
                "mealSnapshot": [{"dishCode": "DISH-001", "dishName": "蒜蓉西兰花"}],
            },
        )
    assert exc_info.value.error_code == ErrorCode.BAD_REQUEST
    assert "meal_snapshot 不能为空" in exc_info.value.detail
    app.dependency_overrides.pop(api_dependencies.get_smart_meal_risk_service, None)


def test_smart_meal_route_maps_service_package_not_found_to_bad_request(monkeypatch) -> None:
    class PackageNotFoundSmartMealRiskService:
        async def identify_risks(self, **kwargs):  # noqa: ANN003, ANN201
            raise SmartMealRiskServiceError("package_not_found: 套餐不存在")

    app = create_test_app()
    app.dependency_overrides[api_dependencies.get_smart_meal_risk_service] = lambda: PackageNotFoundSmartMealRiskService()
    client = TestClient(app)

    with pytest.raises(BusinessError) as exc_info:
        client.post(
            "/api/v1/smart-meal/risk-identify",
            headers={"X-Trace-Id": "trace-001"},
            json={
                "id_card_no": "110101199001011234",
                "campusId": "TJ-001",
                "mealSnapshot": [{"dishCode": "DISH-001", "dishName": "蒜蓉西兰花"}],
            },
        )
    assert exc_info.value.error_code == ErrorCode.BAD_REQUEST
    assert "套餐不存在" in exc_info.value.detail
    app.dependency_overrides.pop(api_dependencies.get_smart_meal_risk_service, None)


def test_smart_meal_route_maps_service_external_timeout_to_timeout(monkeypatch) -> None:
    class TimeoutSmartMealRiskService:
        async def identify_risks(self, **kwargs):  # noqa: ANN003, ANN201
            raise SmartMealRiskServiceError("external_timeout: 食物不耐受接口超时")

    app = create_test_app()
    app.dependency_overrides[api_dependencies.get_smart_meal_risk_service] = lambda: TimeoutSmartMealRiskService()
    client = TestClient(app)

    with pytest.raises(BusinessError) as exc_info:
        client.post(
            "/api/v1/smart-meal/risk-identify",
            headers={"X-Trace-Id": "trace-001"},
            json={
                "id_card_no": "110101199001011234",
                "campusId": "TJ-001",
                "mealSnapshot": [{"dishCode": "DISH-001", "dishName": "蒜蓉西兰花"}],
            },
        )
    assert exc_info.value.error_code == ErrorCode.EXTERNAL_SERVICE_TIMEOUT
    assert "食物不耐受接口超时" in exc_info.value.detail
    app.dependency_overrides.pop(api_dependencies.get_smart_meal_risk_service, None)


def test_smart_meal_route_maps_service_external_failed_to_external_error(monkeypatch) -> None:
    class ExternalFailedSmartMealRiskService:
        async def identify_risks(self, **kwargs):  # noqa: ANN003, ANN201
            raise SmartMealRiskServiceError("external_failed: 食物不耐受接口调用失败")

    app = create_test_app()
    app.dependency_overrides[api_dependencies.get_smart_meal_risk_service] = lambda: ExternalFailedSmartMealRiskService()
    client = TestClient(app)

    with pytest.raises(BusinessError) as exc_info:
        client.post(
            "/api/v1/smart-meal/risk-identify",
            headers={"X-Trace-Id": "trace-001"},
            json={
                "id_card_no": "110101199001011234",
                "campusId": "TJ-001",
                "mealSnapshot": [{"dishCode": "DISH-001", "dishName": "蒜蓉西兰花"}],
            },
        )
    assert exc_info.value.error_code == ErrorCode.EXTERNAL_SERVICE_ERROR
    assert "食物不耐受接口调用失败" in exc_info.value.detail
    app.dependency_overrides.pop(api_dependencies.get_smart_meal_risk_service, None)


def test_smart_meal_route_maps_unexpected_service_error_to_internal_error(monkeypatch) -> None:
    class UnexpectedSmartMealRiskService:
        async def identify_risks(self, **kwargs):  # noqa: ANN003, ANN201
            raise RuntimeError("unexpected")

    app = create_test_app()
    app.dependency_overrides[api_dependencies.get_smart_meal_risk_service] = lambda: UnexpectedSmartMealRiskService()
    client = TestClient(app)

    with pytest.raises(BusinessError) as exc_info:
        client.post(
            "/api/v1/smart-meal/risk-identify",
            headers={"X-Trace-Id": "trace-001"},
            json={
                "id_card_no": "110101199001011234",
                "campusId": "TJ-001",
                "mealSnapshot": [{"dishCode": "DISH-001", "dishName": "蒜蓉西兰花"}],
            },
        )
    assert exc_info.value.error_code == ErrorCode.INTERNAL_ERROR
    assert "智能订餐风险识别失败" in exc_info.value.detail
    app.dependency_overrides.pop(api_dependencies.get_smart_meal_risk_service, None)


def test_smart_meal_route_maps_real_service_empty_normalized_snapshot_to_bad_request(monkeypatch) -> None:
    app = create_test_app()
    app.dependency_overrides[api_dependencies.get_smart_meal_risk_service] = lambda: SmartMealRiskService()
    client = TestClient(app)

    with pytest.raises(BusinessError) as exc_info:
        client.post(
            "/api/v1/smart-meal/risk-identify",
            headers={"X-Trace-Id": "trace-001"},
            json={
                "id_card_no": "110101199001011234",
                "campusId": "TJ-001",
                "mealSnapshot": [{"dishCode": None, "dishName": "会被跳过"}],
            },
        )
    assert exc_info.value.error_code == ErrorCode.BAD_REQUEST
    assert "meal_snapshot 不能为空" in exc_info.value.detail
    app.dependency_overrides.pop(api_dependencies.get_smart_meal_risk_service, None)


def test_smart_meal_route_maps_real_service_empty_string_dish_code_snapshot_to_bad_request(monkeypatch) -> None:
    app = create_test_app()
    app.dependency_overrides[api_dependencies.get_smart_meal_risk_service] = lambda: SmartMealRiskService()
    client = TestClient(app)

    with pytest.raises(BusinessError) as exc_info:
        client.post(
            "/api/v1/smart-meal/risk-identify",
            headers={"X-Trace-Id": "trace-001"},
            json={
                "id_card_no": "110101199001011234",
                "campusId": "TJ-001",
                "mealSnapshot": [{"dishCode": "", "dishName": "会被跳过"}],
            },
        )
    assert exc_info.value.error_code == ErrorCode.BAD_REQUEST
    assert "meal_snapshot 不能为空" in exc_info.value.detail
    app.dependency_overrides.pop(api_dependencies.get_smart_meal_risk_service, None)


def test_smart_meal_route_maps_real_service_blank_string_dish_code_snapshot_to_bad_request(monkeypatch) -> None:
    app = create_test_app()
    app.dependency_overrides[api_dependencies.get_smart_meal_risk_service] = lambda: SmartMealRiskService()
    client = TestClient(app)

    with pytest.raises(BusinessError) as exc_info:
        client.post(
            "/api/v1/smart-meal/risk-identify",
            headers={"X-Trace-Id": "trace-001"},
            json={
                "id_card_no": "110101199001011234",
                "campusId": "TJ-001",
                "mealSnapshot": [{"dishCode": "   ", "dishName": "会被跳过"}],
            },
        )
    assert exc_info.value.error_code == ErrorCode.BAD_REQUEST
    assert "meal_snapshot 不能为空" in exc_info.value.detail
    app.dependency_overrides.pop(api_dependencies.get_smart_meal_risk_service, None)


def test_smart_meal_route_maps_real_service_missing_dish_code_snapshot_to_bad_request(monkeypatch) -> None:
    app = create_test_app()
    app.dependency_overrides[api_dependencies.get_smart_meal_risk_service] = lambda: SmartMealRiskService()
    client = TestClient(app)

    with pytest.raises(BusinessError) as exc_info:
        client.post(
            "/api/v1/smart-meal/risk-identify",
            headers={"X-Trace-Id": "trace-001"},
            json={
                "id_card_no": "110101199001011234",
                "campusId": "TJ-001",
                "mealSnapshot": [{"dishName": "会被跳过"}],
            },
        )
    assert exc_info.value.error_code == ErrorCode.BAD_REQUEST
    assert "meal_snapshot 不能为空" in exc_info.value.detail
    app.dependency_overrides.pop(api_dependencies.get_smart_meal_risk_service, None)


def test_smart_meal_route_maps_real_service_blank_campus_to_bad_request(monkeypatch) -> None:
    app = create_test_app()
    app.dependency_overrides[api_dependencies.get_smart_meal_risk_service] = lambda: SmartMealRiskService()
    client = TestClient(app)

    with pytest.raises(BusinessError) as exc_info:
        client.post(
            "/api/v1/smart-meal/risk-identify",
            headers={"X-Trace-Id": "trace-001"},
            json={
                "id_card_no": "110101199001011234",
                "campusId": "   ",
                "mealSnapshot": [{"dishCode": "DISH-001", "dishName": "蒜蓉西兰花"}],
            },
        )
    assert exc_info.value.error_code == ErrorCode.BAD_REQUEST
    assert "campus_id 不能为空" in exc_info.value.detail
    app.dependency_overrides.pop(api_dependencies.get_smart_meal_risk_service, None)


def test_smart_meal_route_with_real_service_returns_normalized_rule_result(monkeypatch) -> None:
    app = create_test_app()
    service = SmartMealRiskService()

    async def stub_fetch_intolerance_items(**kwargs):  # noqa: ANN003
        return ["芒果特异性IgG抗体（提示）:2级", "牛奶-sIgE抗体升高（轻度）"]

    async def stub_query_meal_dishes(**kwargs):  # noqa: ANN003
        return [
            {
                "campus_id": "TJ-001",
                "dish_code": "DISH-M",
                "dish_name": "芒果沙拉",
                "ingredient_json": [{"ingredientName": "芒果", "ingredientCatagory": "水果"}],
            },
            {
                "campus_id": "TJ-001",
                "dish_code": "DISH-N",
                "dish_name": "牛奶燕麦",
                "ingredient_json": [{"ingredientName": "牛奶", "ingredientCatagory": "奶制品"}],
            },
        ]

    monkeypatch.setattr(service, "_fetch_intolerance_items", stub_fetch_intolerance_items)
    monkeypatch.setattr(service, "_query_meal_dishes", stub_query_meal_dishes)
    app.dependency_overrides[api_dependencies.get_smart_meal_risk_service] = lambda: service
    client = TestClient(app)

    response = client.post(
        "/api/v1/smart-meal/risk-identify",
        headers={"X-Trace-Id": "trace-001"},
        json={
            "id_card_no": "110101199001011234",
            "campusId": "TJ-001",
            "mealSnapshot": [
                {"dishCode": None, "dishName": "芒果沙拉"},
                {"dishCode": "DISH-M", "dishName": "芒果沙拉"},
                {"dishCode": "DISH-N", "dishName": "牛奶燕麦"},
            ],
        },
    )
    assert response.status_code == 200
    assert response.json() == {
        "code": 0,
        "message": "ok",
        "data": [
            {
                "ingredient": "牛奶",
                "intolerance_level": "未知",
                "dishes": [{"dishCode": "DISH-N", "dishName": "牛奶燕麦"}],
            },
            {
                "ingredient": "芒果",
                "intolerance_level": "2级",
                "dishes": [{"dishCode": "DISH-M", "dishName": "芒果沙拉"}],
            },
        ],
    }
    app.dependency_overrides.pop(api_dependencies.get_smart_meal_risk_service, None)


def test_smart_meal_route_with_real_service_deduplicates_and_sorts_dishes(monkeypatch) -> None:
    app = create_test_app()
    service = SmartMealRiskService()

    async def stub_fetch_intolerance_items(**kwargs):  # noqa: ANN003
        return ["西兰花:2级"]

    async def stub_query_meal_dishes(**kwargs):  # noqa: ANN003
        return [
            {
                "campus_id": "TJ-001",
                "dish_code": "DISH-B",
                "dish_name": "西兰花炒虾仁",
                "ingredient_json": [{"ingredientName": "西兰花", "ingredientCatagory": "蔬菜"}],
            },
            {
                "campus_id": "TJ-001",
                "dish_code": "DISH-A",
                "dish_name": "蒜蓉西兰花",
                "ingredient_json": [{"ingredientName": "西兰花", "ingredientCatagory": "蔬菜"}],
            },
            {
                "campus_id": "TJ-001",
                "dish_code": "DISH-A",
                "dish_name": "蒜蓉西兰花",
                "ingredient_json": [{"ingredientName": "西兰花", "ingredientCatagory": "蔬菜"}],
            },
        ]

    monkeypatch.setattr(service, "_fetch_intolerance_items", stub_fetch_intolerance_items)
    monkeypatch.setattr(service, "_query_meal_dishes", stub_query_meal_dishes)
    app.dependency_overrides[api_dependencies.get_smart_meal_risk_service] = lambda: service
    client = TestClient(app)

    response = client.post(
        "/api/v1/smart-meal/risk-identify",
        headers={"X-Trace-Id": "trace-001"},
        json={
            "id_card_no": "110101199001011234",
            "campusId": "TJ-001",
            "mealSnapshot": [
                {"dishCode": "DISH-B", "dishName": "西兰花炒虾仁"},
                {"dishCode": None, "dishName": "会被跳过"},
                {"dishCode": "DISH-A", "dishName": "蒜蓉西兰花"},
                {"dishCode": "DISH-A", "dishName": "蒜蓉西兰花"},
            ],
        },
    )
    assert response.status_code == 200
    assert response.json() == {
        "code": 0,
        "message": "ok",
        "data": [
            {
                "ingredient": "西兰花",
                "intolerance_level": "2级",
                "dishes": [
                    {"dishCode": "DISH-A", "dishName": "蒜蓉西兰花"},
                    {"dishCode": "DISH-B", "dishName": "西兰花炒虾仁"},
                ],
            }
        ],
    }
    app.dependency_overrides.pop(api_dependencies.get_smart_meal_risk_service, None)
