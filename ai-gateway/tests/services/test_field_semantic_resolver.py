from __future__ import annotations

import pytest

from app.services.api_catalog.field_semantic_resolver import ApiFieldSemanticResolver
from app.services.api_catalog.graph_models import (
    SemanticFieldAliasRecord,
    SemanticFieldDictRecord,
    SemanticFieldValueMapRecord,
    SemanticGovernanceSnapshot,
)
from app.services.api_catalog.schema import ApiCatalogEntry, ApiCatalogFieldProfile


class FakeSemanticFieldRepository:
    """字段治理仓储测试桩。"""

    def __init__(self, snapshot: SemanticGovernanceSnapshot) -> None:
        self._snapshot = snapshot
        self.load_calls = 0
        self.closed = False

    async def load_active_rules(self) -> SemanticGovernanceSnapshot:
        self.load_calls += 1
        return self._snapshot

    async def close(self) -> None:
        self.closed = True


def _make_entry(**kwargs) -> ApiCatalogEntry:
    defaults = {
        "id": "entry_1",
        "description": "测试接口",
        "domain": "crm",
        "tag_name": "customer_management",
        "method": "GET",
        "path": "/api/test",
        "operation_safety": "query",
    }
    return ApiCatalogEntry(**{**defaults, **kwargs})


def _request_profile(
    field_name: str,
    *,
    location: str = "body",
    json_path: str | None = None,
    raw_field_type: str | None = "string",
    raw_description: str | None = None,
    required: bool = False,
    array_mode: bool = False,
) -> ApiCatalogFieldProfile:
    return ApiCatalogFieldProfile(
        direction="request",
        location=location,
        field_name=field_name,
        json_path=json_path or f"{location}.{field_name}",
        raw_field_type=raw_field_type,
        raw_description=raw_description,
        required=required,
        array_mode=array_mode,
    )


def _response_profile(
    field_name: str,
    *,
    json_path: str,
    raw_field_type: str | None = "string",
    raw_description: str | None = None,
    array_mode: bool = False,
) -> ApiCatalogFieldProfile:
    return ApiCatalogFieldProfile(
        direction="response",
        location="response",
        field_name=field_name,
        json_path=json_path,
        raw_field_type=raw_field_type,
        raw_description=raw_description,
        array_mode=array_mode,
    )


def _field_dict(semantic_key: str, **kwargs) -> SemanticFieldDictRecord:
    defaults = {
        "standard_key": semantic_key.split(".")[-1],
        "entity_code": semantic_key.split(".")[0],
        "canonical_name": semantic_key.split(".")[-1],
        "label": semantic_key,
        "field_type": "text",
        "value_type": "string",
        "description": semantic_key,
        "graph_role": "identifier",
        "is_identifier": True,
        "is_graph_enabled": True,
    }
    return SemanticFieldDictRecord(semantic_key=semantic_key, **{**defaults, **kwargs})


def _alias(semantic_key: str, alias: str, **kwargs) -> SemanticFieldAliasRecord:
    defaults = {
        "scope_type": "global",
        "scope_value": "*",
        "direction": "both",
        "location": "any",
        "priority": 100,
        "confidence": 1.0,
    }
    return SemanticFieldAliasRecord(semantic_key=semantic_key, alias=alias, **{**defaults, **kwargs})


def _value_map(semantic_key: str, standard_code: str, raw_value: str, **kwargs) -> SemanticFieldValueMapRecord:
    defaults = {
        "scope_type": "global",
        "scope_value": "*",
        "standard_label": standard_code,
    }
    return SemanticFieldValueMapRecord(
        semantic_key=semantic_key,
        standard_code=standard_code,
        raw_value=raw_value,
        **{**defaults, **kwargs},
    )


class TestFieldSemanticResolver:
    def test_resolver_normalizes_request_field_and_filters_pagination_noise(self):
        entry = _make_entry(
            id="role_delete",
            domain="iam",
            tag_name="role_management",
            method="POST",
            path="/system/employee/sys-role/delete",
            operation_safety="mutation",
            request_field_profiles=[
                _request_profile(
                    "roleId",
                    raw_description="角色ID",
                    required=True,
                ),
                _request_profile(
                    "pageSize",
                    raw_field_type="int32",
                    raw_description="分页大小",
                ),
            ],
        )
        snapshot = SemanticGovernanceSnapshot(
            field_dicts=[
                _field_dict(
                    "Role.id",
                    standard_key="id",
                    entity_code="Role",
                    canonical_name="id",
                    label="角色ID",
                    description="角色主键",
                    display_domain_code="role",
                    display_domain_label="角色",
                    display_section_code="basic",
                    display_section_label="基本信息",
                ),
                _field_dict(
                    "System.page_size",
                    standard_key="pageSize",
                    entity_code="System",
                    canonical_name="pageSize",
                    label="分页大小",
                    field_type="number",
                    value_type="integer",
                    description="分页大小",
                    graph_role="pagination",
                    is_identifier=False,
                    is_graph_enabled=False,
                ),
            ],
            aliases=[
                _alias(
                    "Role.id",
                    "roleId",
                    scope_type="api",
                    scope_value="role_delete",
                    direction="request",
                    location="body",
                    priority=1,
                ),
                _alias(
                    "System.page_size",
                    "pageSize",
                    direction="request",
                    location="body",
                    priority=1,
                ),
            ],
        )

        resolver = ApiFieldSemanticResolver()
        bindings = resolver.resolve_entry_bindings(entry, governance_snapshot=snapshot)

        assert len(bindings) == 1
        binding = bindings[0]
        assert binding.semantic_key == "Role.id"
        assert binding.normalized_field_type == "text"
        assert binding.normalized_value_type == "string"
        assert binding.normalized_description == "角色主键"
        assert binding.display_partition_key == "role.basic"
        assert binding.required is True
        assert binding.name_source == "semantic_field_alias:api"

    def test_resolver_prefers_tag_scope_alias_and_degrades_confidence_on_type_conflict(self):
        entry = _make_entry(
            id="customer_list",
            response_field_profiles=[
                _response_profile(
                    "id",
                    json_path="data.records[].id",
                    raw_field_type="int64",
                    raw_description="客户ID",
                    array_mode=True,
                ),
                _response_profile(
                    "status",
                    json_path="data.records[].status",
                    raw_field_type="int32",
                    raw_description="状态",
                    array_mode=True,
                ),
            ],
        )
        snapshot = SemanticGovernanceSnapshot(
            field_dicts=[
                _field_dict(
                    "Generic.id",
                    entity_code="Generic",
                    label="通用ID",
                    description="通用主键",
                ),
                _field_dict(
                    "Customer.id",
                    entity_code="Customer",
                    label="客户ID",
                    description="客户主键",
                    display_domain_code="customer",
                    display_domain_label="客户",
                    display_section_code="basic",
                    display_section_label="基本信息",
                ),
                _field_dict(
                    "Customer.status",
                    entity_code="Customer",
                    canonical_name="status",
                    label="客户状态",
                    field_type="select",
                    value_type="integer",
                    description="客户状态",
                    graph_role="display_only",
                    is_identifier=False,
                    is_graph_enabled=False,
                ),
            ],
            aliases=[
                _alias(
                    "Generic.id",
                    "id",
                    direction="response",
                    location="response",
                    priority=50,
                    confidence=0.7,
                ),
                _alias(
                    "Customer.id",
                    "id",
                    scope_type="tag",
                    scope_value="customer_management",
                    direction="response",
                    location="response",
                    priority=1,
                    confidence=0.95,
                ),
                _alias(
                    "Customer.status",
                    "status",
                    scope_type="tag",
                    scope_value="customer_management",
                    direction="response",
                    location="response",
                    priority=1,
                ),
            ],
            value_maps=[
                _value_map(
                    "Customer.id",
                    "customer_id",
                    "1",
                    scope_type="tag",
                    scope_value="customer_management",
                    standard_label="客户ID",
                )
            ],
        )

        resolver = ApiFieldSemanticResolver()
        bindings = resolver.resolve_entry_bindings(entry, governance_snapshot=snapshot)

        assert len(bindings) == 1
        binding = bindings[0]
        assert binding.semantic_key == "Customer.id"
        assert binding.display_partition_key == "customer.basic"
        assert binding.name_source == "semantic_field_alias:tag"
        assert binding.array_mode is True
        assert binding.confidence == pytest.approx(0.35)
        assert binding.value_mapping_rule == {
            "mapping_count": 1,
            "standard_codes": ["customer_id"],
            "top_scope_type": "tag",
            "top_scope_value": "customer_management",
        }

    def test_resolver_uses_field_dict_fallback_when_alias_is_missing_and_match_is_unique(self):
        entry = _make_entry(
            request_field_profiles=[
                _request_profile(
                    "mobilePhone",
                    location="queryParams",
                    raw_description="手机号",
                )
            ]
        )
        snapshot = SemanticGovernanceSnapshot(
            field_dicts=[
                _field_dict(
                    "Customer.mobile_phone",
                    standard_key="mobilePhone",
                    entity_code="Customer",
                    canonical_name="mobilePhone",
                    label="手机号",
                    description="客户手机号",
                    business_domain="crm",
                    graph_role="locator",
                    is_identifier=False,
                )
            ]
        )

        resolver = ApiFieldSemanticResolver()
        bindings = resolver.resolve_entry_bindings(entry, governance_snapshot=snapshot)

        assert len(bindings) == 1
        binding = bindings[0]
        assert binding.semantic_key == "Customer.mobile_phone"
        assert binding.source == "field_dict"
        assert binding.name_source == "field_dict_fallback"
        assert binding.type_source == "semantic_field_dict"
        assert binding.description_source == "semantic_field_dict"

    def test_resolver_supports_alias_scope_value_map(self):
        """`scope_type=alias` 应按字段原名命中值域映射，避免跨字段污染枚举解释。"""

        entry = _make_entry(
            request_field_profiles=[
                _request_profile(
                    "sex_code",
                    location="body",
                    raw_field_type="string",
                    raw_description="性别编码",
                )
            ]
        )
        snapshot = SemanticGovernanceSnapshot(
            field_dicts=[
                _field_dict(
                    "Customer.gender",
                    standard_key="gender",
                    entity_code="Customer",
                    canonical_name="gender",
                    label="性别",
                    field_type="select",
                    value_type="string",
                    graph_role="locator",
                    is_identifier=False,
                    is_graph_enabled=True,
                )
            ],
            aliases=[
                _alias(
                    "Customer.gender",
                    "sex_code",
                    direction="request",
                    location="body",
                )
            ],
            value_maps=[
                _value_map(
                    "Customer.gender",
                    "male",
                    "1",
                    scope_type="alias",
                    scope_value="sex_code",
                    standard_label="男",
                ),
                _value_map(
                    "Customer.gender",
                    "female",
                    "2",
                    scope_type="alias",
                    scope_value="sex_code",
                    standard_label="女",
                    sort_order=1,
                ),
            ],
        )

        resolver = ApiFieldSemanticResolver()
        bindings = resolver.resolve_entry_bindings(entry, governance_snapshot=snapshot)

        assert len(bindings) == 1
        binding = bindings[0]
        assert binding.semantic_key == "Customer.gender"
        assert binding.value_mapping_rule == {
            "mapping_count": 2,
            "standard_codes": ["male", "female"],
            "top_scope_type": "alias",
            "top_scope_value": "sex_code",
        }

    def test_resolver_prefers_domain_scope_alias_over_global_alias(self):
        entry = _make_entry(
            domain="iam",
            request_field_profiles=[_request_profile("deptId", raw_description="部门ID")]
        )
        snapshot = SemanticGovernanceSnapshot(
            field_dicts=[
                _field_dict(
                    "Generic.id",
                    entity_code="Generic",
                    label="通用ID",
                    description="通用主键",
                ),
                _field_dict(
                    "Department.id",
                    entity_code="Department",
                    label="部门ID",
                    description="部门主键",
                ),
            ],
            aliases=[
                _alias(
                    "Generic.id",
                    "deptId",
                    direction="request",
                    location="body",
                    priority=50,
                    confidence=0.5,
                ),
                _alias(
                    "Department.id",
                    "deptId",
                    scope_type="domain",
                    scope_value="iam",
                    direction="request",
                    location="body",
                    priority=50,
                    confidence=0.9,
                ),
            ],
        )

        resolver = ApiFieldSemanticResolver()
        bindings = resolver.resolve_entry_bindings(entry, governance_snapshot=snapshot)

        assert len(bindings) == 1
        binding = bindings[0]
        assert binding.semantic_key == "Department.id"
        assert binding.name_source == "semantic_field_alias:domain"
        assert binding.confidence == pytest.approx(0.9)

    def test_resolver_honors_json_path_pattern_for_same_named_fields(self):
        entry = _make_entry(
            response_field_profiles=[
                _response_profile(
                    "id",
                    json_path="data.records[].owner.id",
                    raw_description="归属人ID",
                )
            ]
        )
        snapshot = SemanticGovernanceSnapshot(
            field_dicts=[
                _field_dict(
                    "Customer.id",
                    entity_code="Customer",
                    label="客户ID",
                    description="客户主键",
                ),
                _field_dict(
                    "Employee.id",
                    entity_code="Employee",
                    label="员工ID",
                    description="员工主键",
                ),
            ],
            aliases=[
                _alias(
                    "Customer.id",
                    "id",
                    direction="response",
                    location="response",
                    json_path_pattern="data.records[*].customer.id",
                ),
                _alias(
                    "Employee.id",
                    "id",
                    direction="response",
                    location="response",
                    json_path_pattern="data.records[*].owner.id",
                ),
            ],
        )

        resolver = ApiFieldSemanticResolver()
        bindings = resolver.resolve_entry_bindings(entry, governance_snapshot=snapshot)

        assert len(bindings) == 1
        assert bindings[0].semantic_key == "Employee.id"

    def test_resolver_filters_common_noise_fields_even_when_graph_flags_allow_it(self):
        entry = _make_entry(
            response_field_profiles=[
                _response_profile(
                    "status",
                    json_path="data.records[].status",
                    raw_field_type="int32",
                    raw_description="状态",
                    array_mode=True,
                ),
                _response_profile(
                    "updateTime",
                    json_path="data.records[].updateTime",
                    raw_field_type="datetime",
                    raw_description="更新时间",
                    array_mode=True,
                ),
            ]
        )
        snapshot = SemanticGovernanceSnapshot(
            field_dicts=[
                _field_dict(
                    "Customer.status",
                    entity_code="Customer",
                    canonical_name="status",
                    label="客户状态",
                    field_type="select",
                    value_type="integer",
                    description="客户状态",
                    graph_role="locator",
                    is_identifier=False,
                    is_graph_enabled=True,
                ),
                _field_dict(
                    "Customer.update_time",
                    standard_key="updateTime",
                    entity_code="Customer",
                    canonical_name="updateTime",
                    label="更新时间",
                    field_type="date",
                    value_type="datetime",
                    description="更新时间",
                    graph_role="bridge",
                    is_identifier=False,
                    is_graph_enabled=True,
                ),
            ],
            aliases=[
                _alias(
                    "Customer.status",
                    "status",
                    direction="response",
                    location="response",
                ),
                _alias(
                    "Customer.update_time",
                    "updateTime",
                    direction="response",
                    location="response",
                ),
            ],
        )

        resolver = ApiFieldSemanticResolver()
        bindings = resolver.resolve_entry_bindings(entry, governance_snapshot=snapshot)

        assert bindings == []

    @pytest.mark.asyncio
    async def test_resolve_bindings_loads_governance_snapshot_once_from_repository(self):
        snapshot = SemanticGovernanceSnapshot(
            field_dicts=[
                _field_dict(
                    "Role.id",
                    entity_code="Role",
                    label="角色ID",
                    description="角色主键",
                )
            ],
            aliases=[
                _alias(
                    "Role.id",
                    "roleId",
                    direction="request",
                    location="body",
                )
            ],
        )
        repository = FakeSemanticFieldRepository(snapshot)
        resolver = ApiFieldSemanticResolver(repository=repository)
        entries = [
            _make_entry(id="role_delete_1", request_field_profiles=[_request_profile("roleId")]),
            _make_entry(id="role_delete_2", request_field_profiles=[_request_profile("roleId")]),
        ]

        bindings = await resolver.resolve_bindings(entries)

        assert len(bindings) == 2
        assert repository.load_calls == 1

    @pytest.mark.asyncio
    async def test_load_governance_snapshot_and_close_delegate_to_repository(self):
        snapshot = SemanticGovernanceSnapshot()
        repository = FakeSemanticFieldRepository(snapshot)
        resolver = ApiFieldSemanticResolver(repository=repository)

        loaded_snapshot = await resolver.load_governance_snapshot()
        await resolver.close()

        assert loaded_snapshot is snapshot
        assert repository.load_calls == 1
        assert repository.closed is True
