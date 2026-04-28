from __future__ import annotations

import pytest

from app.models.schemas import SemanticCurationPhase
from app.services.api_catalog.graph_models import (
    SemanticFieldAliasRecord,
    SemanticFieldDictRecord,
    SemanticGovernanceSnapshot,
)
from app.services.api_catalog.schema import ApiCatalogEntry, ApiCatalogFieldProfile
from app.services.api_catalog.semantic_governance_proposal_service import SemanticGovernanceProposalService
from app.services.api_catalog.semantic_governance_proposal_models import UiBlueprintSectionRule, UiBlueprintSnapshot


class _StubUiBlueprintRepository:
    def __init__(self, snapshot: UiBlueprintSnapshot | None = None) -> None:
        self._snapshot = snapshot or UiBlueprintSnapshot()

    async def load_snapshot(self) -> UiBlueprintSnapshot:
        return self._snapshot

    async def close(self) -> None:
        return None


def _entry(**kwargs) -> ApiCatalogEntry:
    defaults = {
        "id": "api_customer_list",
        "description": "客户列表",
        "domain": "customer",
        "method": "GET",
        "path": "/api/customer/list",
        "operation_safety": "query",
    }
    return ApiCatalogEntry(**{**defaults, **kwargs})


def _request_profile(name: str, *, description: str | None = None, raw_type: str | None = "string") -> ApiCatalogFieldProfile:
    return ApiCatalogFieldProfile(
        direction="request",
        location="queryParams",
        field_name=name,
        json_path=f"queryParams.{name}",
        raw_field_type=raw_type,
        raw_description=description,
    )


@pytest.mark.asyncio
async def test_build_batch_prefers_existing_alias_for_fast_path() -> None:
    service = SemanticGovernanceProposalService(ui_blueprint_repository=_StubUiBlueprintRepository())
    entry = _entry(request_field_profiles=[_request_profile("customerId", description="客户ID")])
    snapshot = SemanticGovernanceSnapshot(
        field_dicts=[
            SemanticFieldDictRecord(
                semantic_key="Customer.id",
                standard_key="id",
                entity_code="Customer",
                canonical_name="id",
                label="客户ID",
                graph_role="identifier",
                is_identifier=True,
                is_graph_enabled=True,
            )
        ],
        aliases=[
            SemanticFieldAliasRecord(
                semantic_key="Customer.id",
                alias="customerId",
                scope_type="global",
                scope_value="*",
                direction="request",
                location="queryParams",
                priority=100,
                confidence=1.0,
                is_active=True,
            )
        ],
    )

    batch = await service.build_batch(
        entries=[entry],
        phase=SemanticCurationPhase.PLAN_B,
        governance_snapshot=snapshot,
    )

    assert batch.total_fields == 1
    assert batch.high_confidence_fields == 1
    assert batch.pending_fields == 0
    assert batch.dict_proposals == []
    assert len(batch.alias_proposals) == 1
    assert batch.alias_proposals[0].semantic_key == "Customer.id"
    assert batch.alias_proposals[0].review_status == "approved"


@pytest.mark.asyncio
async def test_build_batch_generates_dict_alias_and_value_map_for_new_field() -> None:
    service = SemanticGovernanceProposalService(
        auto_approve_confidence=0.95,
        ui_blueprint_repository=_StubUiBlueprintRepository(),
    )
    entry = _entry(
        id="api_patient_create",
        domain="patient",
        request_field_profiles=[
            _request_profile("sex_code", description="1:男,2:女"),
            _request_profile("patientId", description="患者ID"),
        ],
    )

    batch = await service.build_batch(
        entries=[entry],
        phase=SemanticCurationPhase.PLAN_C,
        governance_snapshot=SemanticGovernanceSnapshot(),
    )

    assert batch.total_fields == 2
    assert len(batch.dict_proposals) >= 2
    assert any(proposal.semantic_key.endswith(".sex_code") for proposal in batch.dict_proposals)
    assert any(proposal.semantic_key.endswith(".patient_id") for proposal in batch.dict_proposals)
    assert any(proposal.review_status == "pending" for proposal in batch.dict_proposals)
    assert len(batch.alias_proposals) >= 2
    assert len(batch.value_map_proposals) == 2
    assert {proposal.standard_code for proposal in batch.value_map_proposals} == {"male", "female"}


@pytest.mark.asyncio
async def test_build_batch_uses_ui_blueprint_dict_partition_mapping() -> None:
    """命中 ui_blueprint_dict 的 typical_fields 时，应优先采用分区字典规则。"""

    blueprint_snapshot = UiBlueprintSnapshot(
        rules=[
            UiBlueprintSectionRule(
                display_domain_code="customer",
                display_domain_label="客户档案",
                display_section_code="basic_info",
                display_section_label="基本信息",
                typical_fields=["customer_id", "name", "gender"],
                priority=10,
                is_active=True,
            ),
            UiBlueprintSectionRule(
                display_domain_code="customer",
                display_domain_label="客户档案",
                display_section_code="market_owner",
                display_section_label="市场归属信息",
                typical_fields=["market_teacher_name", "market_region"],
                priority=20,
                is_active=True,
            ),
        ]
    )
    service = SemanticGovernanceProposalService(
        ui_blueprint_repository=_StubUiBlueprintRepository(snapshot=blueprint_snapshot),
    )
    entry = _entry(
        id="api_customer_detail",
        domain="customer",
        request_field_profiles=[
            _request_profile("marketTeacherName", description="市场老师姓名"),
        ],
    )

    batch = await service.build_batch(
        entries=[entry],
        phase=SemanticCurationPhase.PLAN_B,
        governance_snapshot=SemanticGovernanceSnapshot(),
    )

    assert len(batch.dict_proposals) == 1
    dict_proposal = batch.dict_proposals[0]
    assert dict_proposal.display_domain_code == "customer"
    assert dict_proposal.display_domain_label == "客户档案"
    assert dict_proposal.display_section_code == "market_owner"
    assert dict_proposal.display_section_label == "市场归属信息"
