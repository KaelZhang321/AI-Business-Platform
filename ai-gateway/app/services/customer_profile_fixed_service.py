from __future__ import annotations

import logging
import re
import zipfile
from dataclasses import dataclass, field
from functools import lru_cache
from html import unescape
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from app.models.schemas import (
    ApiQueryExecutionPlan,
    ApiQueryExecutionResult,
    ApiQueryExecutionStatus,
    ApiQueryPlanStep,
    ApiQueryRequest,
    ApiQueryResponse,
)
from app.services.api_catalog.executor import ApiExecutor
from app.services.api_catalog.schema import (
    ApiCatalogDetailViewMeta,
    ApiCatalogEntry,
    ApiCatalogPredecessorParamBinding,
    ApiCatalogPredecessorSpec,
    ParamSchema,
)
from app.utils.json_utils import load_json_object, load_json_value

logger = logging.getLogger(__name__)

_CUSTOMER_LOOKUP_API_ID = "6bbc18329c3dde651603182a651569ab"
_CUSTOMER_PROFILE_PLAN_ID = "dag_customer_profile_fixed"
_CUSTOMER_PROFILE_RENDER_MODE = "customer_profile_fixed"
_DEFAULT_PAGE_NO = 1
_DEFAULT_PAGE_SIZE = 10
_RESOURCE_PATH = Path(__file__).resolve().parents[2] / "resources" / "ui_api_endpoints.xlsx"

_PROFILE_KEYWORDS = (
    "客户信息",
    "客户资料",
    "客户档案",
    "个人信息",
    "个人资料",
    "基础信息",
    "基础资料",
    "身份信息",
    "联系方式",
    "联系信息",
    "电子档案",
    "客户画像",
    "完整资料",
    "全部资料",
    "客户详情",
    "详细信息",
    "健康档案",
    "客户概况",
    "客户总览",
    "客户全貌",
)

_EXCLUDED_SINGLE_TOPIC_KEYWORDS = (
    "储值",
    "项目金",
    "规划方案",
    "历史购买",
    "资产概览",
    "余额",
    "剩余金额",
)

_PROFILE_SECTION_ORDER = (
    ("identity_contact", "一、身份与联系信息", "0f8095e4adbf36aff9c9c03fa00e6ae2"),
    ("health_basic", "二、健康基础数据", "0dee49c62d09654d0762e785af389448"),
    ("health_status_medical_history", "三、健康状况与医疗史", "060811e41afe85711ff9506163270f03"),
    ("physical_exam", "四、体检情况", "5b413b7dbadfd4296e0b116f486b3f82"),
    ("lifestyle_habits", "五、生活方式与习惯", "f5c8f5fbe235ccfd7709b3b3aacc7aac"),
    ("psychology_emotion", "六、心理与情绪", "6a23d924c321dcf0e497853a529d14ea"),
    ("personal_preferences", "七、个人喜好与优势", "64d1e630e1528f6a54de48aac0d05f22"),
    ("health_goals_pain_points", "八、健康目标与核心痛点", "a1cb957146b519d1b6bb81c0f791550e"),
    ("consumption_background", "九、消费能力与背景", "348b5fe307fc9ce132fc169f1f0f4809"),
    ("service_relationship", "十、客户关系与服务记录", "f6b31bd13027951cd20ae199600d2c9c"),
    ("education_records", "十一、教育铺垫记录", "272d276935627e6fdd241b8995b0e8d6"),
    ("notice", "十二、注意事项", "91957d29162df68b3cfe97ac9d831bf4"),
    ("consultation_analysis", "十三、综合分析及咨询记录", "9b7c02932bbf582615026f74595183b8"),
    ("remark", "十四、备注", "7df31026c1502783990268e873e98b5d"),
    ("owner_execution_date", "十五、负责人及执行日期", "40b083c05720a091e0d05c9a8d5db6f9"),
    ("asset_overview", "十六、历史购买储值方案/规划方案/剩余项目金", "fa969d461ef059ab82f1dd6d3c2aa116"),
)

_CANDIDATE_TABLE_FIELDS = (
    ("name", "客户姓名"),
    ("id", "客户ID"),
    ("phoneObfuscated", "脱敏手机号"),
    ("idCardObfuscated", "脱敏身份证号"),
    ("sex", "性别"),
    ("age", "年龄"),
    ("storeName", "所属店铺"),
    ("healthyStewardName", "健康管理师"),
    ("mainDoctorName", "主诊医生"),
    ("mainTeacherName", "主市场老师"),
)

_CUSTOMER_NAME_PATTERNS = (
    re.compile(r"客户(?!信息|资料|档案|画像|详情|概况|总览|全貌)(?P<name>[\u4e00-\u9fa5A-Za-z0-9·]{2,20})"),
    re.compile(r"(?:查询|查看|展示)(?P<name>[\u4e00-\u9fa5A-Za-z0-9·]{2,20})(?:的)?(?:客户|个人|健康|电子|完整|全部|详细)"),
)
_PHONE_PATTERN = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
_ID_CARD_PATTERN = re.compile(r"(?<![0-9A-Za-z])\d{17}[0-9Xx](?![0-9A-Za-z])")
_CUSTOMER_ID_PATTERN = re.compile(r"(?:客户ID|客户编号|customerId)[:：\s]*(?P<id>[0-9A-Za-z_-]{4,64})", re.IGNORECASE)

_XLSX_NS = {
    "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "rel": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "pkg": "http://schemas.openxmlformats.org/package/2006/relationships",
}


@dataclass(frozen=True, slots=True)
class CustomerProfileSection:
    """固定客户档案分区定义。

    功能：把业务确认过的展示顺序、接口 ID 和组件语义绑定成稳定配置。

    Args:
        key: UI Spec 内部使用的分区键，必须稳定且适合前端定位。
        title: 用户在卡片上看到的大标题，来自业务图片顺序。
        api_id: 对应 `ui_api_endpoints.xlsx` 中的接口主键。

    Returns:
        该对象只作为配置项参与计划和渲染，不直接返回给前端。

    Edge Cases:
        若 Excel 缺失某个 active 接口，调用方会跳过该分区并记录日志，避免整页失败。
    """

    key: str
    title: str
    api_id: str


@dataclass(frozen=True, slots=True)
class CustomerProfileTrigger:
    """客户档案固定分支的触发结果。

    功能：承载命中的关键词和客户身份线索，避免后续执行阶段重新解析自然语言。

    Args:
        keyword: 命中的客户档案关键词。
        customer_value: 首跳客户查询使用的客户线索。
        identifier_type: 线索类型，例如 `name`、`phone`、`id_card`、`customer_id`。

    Returns:
        命中时由识别器返回；未命中时返回 `None`。

    Edge Cases:
        单项查询如“储值方案”会被排除，防止固定档案页抢走更精确的业务查询。
    """

    keyword: str
    customer_value: str
    identifier_type: str


@dataclass(slots=True)
class CustomerProfileEndpointCatalog:
    """固定客户档案接口目录快照。

    功能：从 Excel active endpoint 元数据构建只读目录，保证固定分支不依赖 Milvus 召回或 LLM 规划。

    Args:
        entries_by_id: `api_id -> ApiCatalogEntry` 的稳定映射。
        sections: 已按业务大标题排序的展示分区。

    Returns:
        服务内部复用的目录快照。

    Edge Cases:
        目录文件缺失或格式损坏时会抛出 `CustomerProfileCatalogError`，由固定分支降级回通用链路。
    """

    entries_by_id: dict[str, ApiCatalogEntry]
    sections: list[CustomerProfileSection] = field(default_factory=list)

    @property
    def customer_lookup_entry(self) -> ApiCatalogEntry | None:
        return self.entries_by_id.get(_CUSTOMER_LOOKUP_API_ID)


class CustomerProfileCatalogError(RuntimeError):
    """固定客户档案目录加载失败。"""


class CustomerProfileFixedService:
    """客户个人信息固定 UI Spec 服务。

    功能：在 `/api/v1/api-query` 中识别客户档案查询，绕过通用召回与 LLM 规划，按固定接口清单返回
    稳定的客户档案 UI；若首跳客户查询出现重名或多候选，则先返回 wait-select 候选表。

    Args:
        catalog_path: `ui_api_endpoints.xlsx` 的路径；测试可传入临时文件或 monkeypatch 加载函数。

    Returns:
        `handle()` 命中固定分支时返回 `ApiQueryResponse`，未命中或目录不可用时返回 `None`。

    Edge Cases:
        - Excel 资源不可用时不阻断通用 `/api-query` 链路。
        - 多候选客户必须先让用户选择，避免把整套档案接口扩散到多个客户。
        - 用户续跑时仍会执行一次首跳查询，但后续绑定只使用用户选中的候选行。
    """

    def __init__(self, catalog_path: Path | None = None) -> None:
        self._catalog_path = catalog_path or _RESOURCE_PATH

    async def handle(
        self,
        *,
        request_body: ApiQueryRequest,
        executor: ApiExecutor,
        user_token: str | None,
        user_id: str | None,
        trace_id: str,
    ) -> ApiQueryResponse | None:
        """尝试处理客户档案固定分支。

        Args:
            request_body: 当前 `/api-query` 请求体，必须包含自然语言 query。
            executor: 业务接口执行器，用于调用首跳客户查询和档案接口。
            user_token: 透传给业务系统的认证头。
            user_id: 当前用户 ID，用于 runtime invoke 审计字段。
            trace_id: 当前链路追踪 ID。

        Returns:
            命中固定分支时返回完整响应；未命中或目录不可用时返回 `None` 交还通用链路。

        Edge Cases:
            - 查询缺少客户身份线索时不命中固定分支。
            - 首跳返回多条客户时返回 `SKIPPED` 等待态，不执行下游档案接口。
        """
        trigger = detect_customer_profile_trigger(request_body.query)
        if trigger is None:
            return None

        try:
            catalog = load_customer_profile_catalog(self._catalog_path)
        except CustomerProfileCatalogError as exc:
            logger.warning(
                "customer profile fixed catalog unavailable trace_id=%s path=%s error=%s",
                trace_id,
                self._catalog_path,
                exc,
            )
            return None

        lookup_entry = catalog.customer_lookup_entry
        if lookup_entry is None:
            logger.warning("customer profile fixed catalog missing lookup endpoint trace_id=%s", trace_id)
            return None

        lookup_params = build_customer_lookup_params(trigger)
        lookup_result = await executor.call(
            lookup_entry,
            lookup_params,
            user_token=user_token,
            trace_id=trace_id,
            user_id=user_id,
        )
        lookup_rows = normalize_result_rows(lookup_result.data)
        plan_steps = [
            ApiQueryPlanStep(
                step_id="step_get_customer_info",
                api_id=lookup_entry.id,
                api_path=lookup_entry.path,
                params=lookup_params,
                depends_on=[],
            )
        ]

        if lookup_result.status == ApiQueryExecutionStatus.ERROR:
            return build_customer_profile_error_response(
                trace_id=trace_id,
                plan=ApiQueryExecutionPlan(plan_id=_CUSTOMER_PROFILE_PLAN_ID, steps=plan_steps),
                title=f"查询客户{trigger.customer_value}的个人信息",
                message=lookup_result.error or "客户主查询失败",
                status=ApiQueryExecutionStatus.ERROR,
            )
        if not lookup_rows:
            return build_customer_profile_error_response(
                trace_id=trace_id,
                plan=ApiQueryExecutionPlan(plan_id=_CUSTOMER_PROFILE_PLAN_ID, steps=plan_steps),
                title=f"查询客户{trigger.customer_value}的个人信息",
                message="未找到匹配客户，请补充手机号、身份证号或客户ID后重试。",
                status=ApiQueryExecutionStatus.EMPTY,
            )

        selected_customer = resolve_selected_customer(
            rows=lookup_rows,
            selection_context=request_body.selection_context,
            trigger=trigger,
        )
        if selected_customer is None:
            return build_wait_select_response(
                trace_id=trace_id,
                query=request_body.query,
                trigger=trigger,
                lookup_entry=lookup_entry,
                lookup_rows=lookup_rows,
                lookup_params=lookup_params,
                plan=ApiQueryExecutionPlan(plan_id=_CUSTOMER_PROFILE_PLAN_ID, steps=plan_steps),
            )

        section_results: list[tuple[CustomerProfileSection, ApiCatalogEntry, ApiQueryExecutionResult, dict[str, Any]]] = []
        for section in catalog.sections:
            entry = catalog.entries_by_id.get(section.api_id)
            if entry is None or entry.id == _CUSTOMER_LOOKUP_API_ID:
                continue
            params = build_section_params(entry, selected_customer)
            plan_steps.append(
                ApiQueryPlanStep(
                    step_id=f"step_{section.key}",
                    api_id=entry.id,
                    api_path=entry.path,
                    params=params,
                    depends_on=["step_get_customer_info"],
                )
            )
            section_result = await executor.call(
                entry,
                params,
                user_token=user_token,
                trace_id=trace_id,
                user_id=user_id,
            )
            section_results.append((section, entry, section_result, params))

        return build_customer_profile_success_response(
            trace_id=trace_id,
            query=request_body.query,
            trigger=trigger,
            selected_customer=selected_customer,
            plan=ApiQueryExecutionPlan(plan_id=_CUSTOMER_PROFILE_PLAN_ID, steps=plan_steps),
            section_results=section_results,
        )


def detect_customer_profile_trigger(query: str) -> CustomerProfileTrigger | None:
    """识别客户档案固定分支触发条件。

    Args:
        query: 用户自然语言输入。

    Returns:
        命中关键词且存在客户身份线索时返回触发信息；否则返回 `None`。

    Edge Cases:
        - “客户信息怎么维护”只有关键词没有客户线索，不进入固定分支。
        - “查询客户刘海坚的储值方案”属于单项资产查询，交给原通用链路处理。
    """
    normalized_query = (query or "").strip()
    if not normalized_query:
        return None

    keyword = next((item for item in _PROFILE_KEYWORDS if item in normalized_query), "")
    if not keyword:
        return None
    if any(item in normalized_query for item in _EXCLUDED_SINGLE_TOPIC_KEYWORDS):
        return None

    explicit_customer_id = _CUSTOMER_ID_PATTERN.search(normalized_query)
    if explicit_customer_id:
        return CustomerProfileTrigger(keyword=keyword, customer_value=explicit_customer_id.group("id"), identifier_type="customer_id")

    id_card = _ID_CARD_PATTERN.search(normalized_query)
    if id_card:
        return CustomerProfileTrigger(keyword=keyword, customer_value=id_card.group(0), identifier_type="id_card")

    phone = _PHONE_PATTERN.search(normalized_query)
    if phone:
        return CustomerProfileTrigger(keyword=keyword, customer_value=phone.group(0), identifier_type="phone")

    for pattern in _CUSTOMER_NAME_PATTERNS:
        match = pattern.search(normalized_query)
        if match:
            customer_name = _clean_customer_name(match.group("name"))
            if customer_name:
                return CustomerProfileTrigger(keyword=keyword, customer_value=customer_name, identifier_type="name")
    return None


def load_customer_profile_catalog(path: Path = _RESOURCE_PATH) -> CustomerProfileEndpointCatalog:
    """加载客户档案固定分支的 active endpoint 目录。

    Args:
        path: `ui_api_endpoints.xlsx` 文件路径。

    Returns:
        只包含 active endpoint 的客户档案目录快照。

    Edge Cases:
        - `.xlsx` 是 zip + XML 容器，这里用标准库读取，避免为单个固定分支新增运行时依赖。
        - Excel 中缺少非关键分区时允许跳过；缺少首跳客户查询时由调用方降级通用链路。
    """
    return _load_customer_profile_catalog_cached(str(path))


@lru_cache(maxsize=4)
def _load_customer_profile_catalog_cached(path_text: str) -> CustomerProfileEndpointCatalog:
    path = Path(path_text)
    if not path.exists():
        raise CustomerProfileCatalogError(f"catalog file not found: {path}")

    rows = read_xlsx_rows(path)
    if not rows:
        raise CustomerProfileCatalogError(f"catalog file is empty: {path}")
    header = [str(value or "").strip() for value in rows[0]]
    index = {name: position for position, name in enumerate(header) if name}
    required_columns = {"id", "name", "path", "method", "summary", "status", "operation_safety"}
    missing_columns = sorted(required_columns - set(index))
    if missing_columns:
        raise CustomerProfileCatalogError(f"catalog missing columns: {', '.join(missing_columns)}")

    entries_by_id: dict[str, ApiCatalogEntry] = {}
    for row in rows[1:]:
        status = _cell(row, index, "status").lower()
        if status != "active":
            continue
        entry = build_catalog_entry_from_xlsx_row(row, index)
        entries_by_id[entry.id] = entry

    sections = [
        CustomerProfileSection(key=key, title=title, api_id=api_id)
        for key, title, api_id in _PROFILE_SECTION_ORDER
        if api_id in entries_by_id and api_id != _CUSTOMER_LOOKUP_API_ID
    ]
    return CustomerProfileEndpointCatalog(entries_by_id=entries_by_id, sections=sections)


def read_xlsx_rows(path: Path) -> list[list[Any]]:
    """用标准库读取 `.xlsx` 第一张工作表的单元格矩阵。

    Args:
        path: Excel 文件路径。

    Returns:
        按行排列的单元格值矩阵，空白单元格以 `None` 表示。

    Edge Cases:
        - 只解析 sharedStrings 与 inlineStr/string/number，覆盖当前元数据文件形态。
        - 公式单元格若没有缓存值会返回 `None`，固定分支元数据不依赖公式。
    """
    with zipfile.ZipFile(path) as archive:
        shared_strings = _read_shared_strings(archive)
        workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
        first_sheet = workbook.find("main:sheets/main:sheet", _XLSX_NS)
        if first_sheet is None:
            return []
        relationship_id = first_sheet.attrib.get(f"{{{_XLSX_NS['rel']}}}id")
        sheet_path = _resolve_sheet_path(archive, relationship_id)
        worksheet = ElementTree.fromstring(archive.read(sheet_path))

    rows: list[list[Any]] = []
    for row_node in worksheet.findall("main:sheetData/main:row", _XLSX_NS):
        values_by_index: dict[int, Any] = {}
        for cell in row_node.findall("main:c", _XLSX_NS):
            ref = cell.attrib.get("r", "")
            column_index = _column_index_from_ref(ref)
            if column_index < 0:
                continue
            values_by_index[column_index] = _read_cell_value(cell, shared_strings)
        if values_by_index:
            max_index = max(values_by_index)
            rows.append([values_by_index.get(index) for index in range(max_index + 1)])
    return rows


def build_catalog_entry_from_xlsx_row(row: list[Any], index: dict[str, int]) -> ApiCatalogEntry:
    """把 Excel 行转换成 `ApiCatalogEntry`。

    Args:
        row: Excel 当前数据行。
        index: 表头字段到列下标的映射。

    Returns:
        可直接用于执行器调用和固定 UI 渲染的目录对象。

    Edge Cases:
        Excel 中 JSON 列允许为空或非法；非法时回退为空 schema/meta，避免目录加载整体失败。
    """
    request_schema = load_json_object(_cell(row, index, "request_schema"))
    response_schema = load_json_object(_cell(row, index, "response_schema"))
    sample_request = load_json_object(_cell(row, index, "sample_request"))
    predecessor_specs = parse_predecessor_specs(_cell(row, index, "predecessor_specs"))
    detail_view_meta = parse_detail_view_meta(_cell(row, index, "detail_view_meta"))

    return ApiCatalogEntry(
        id=_cell(row, index, "id"),
        name=_cell(row, index, "name"),
        description=_cell(row, index, "summary") or _cell(row, index, "name"),
        domain="customer_profile",
        status="active",
        operation_safety=_normalize_operation_safety(_cell(row, index, "operation_safety")),
        method=_normalize_method(_cell(row, index, "method")),
        path=_cell(row, index, "path"),
        auth_required=True,
        executor_config={"executor_type": "runtime_invoke", "source_id": _cell(row, index, "source_id")},
        param_schema=to_param_schema(request_schema),
        response_schema=response_schema,
        sample_request=sample_request,
        response_data_path=infer_response_data_path(response_schema),
        # 固定档案分支后续还要按原始字段做 predecessor 绑定和 detail_view_meta 取值；
        # 中文展示名只在 UI 组装阶段使用 schema description 解析，不能提前改写数据键。
        field_labels={},
        detail_view_meta=detail_view_meta,
        predecessors=predecessor_specs,
    )


def build_customer_lookup_params(trigger: CustomerProfileTrigger) -> dict[str, Any]:
    """构造首跳客户查询参数。

    Args:
        trigger: 已解析出的客户身份线索。

    Returns:
        `/customerInquiry/getCustomerInfo` 的最小查询参数。

    Edge Cases:
        无论线索类型是什么，都同时写入 `customerInfo`，因为业务接口说明该字段支持姓名、手机号和证件号。
    """
    return {"customerInfo": trigger.customer_value, "pageNo": _DEFAULT_PAGE_NO, "pageSize": _DEFAULT_PAGE_SIZE}


def resolve_selected_customer(
    *,
    rows: list[dict[str, Any]],
    selection_context: dict[str, Any] | None,
    trigger: CustomerProfileTrigger,
) -> dict[str, Any] | None:
    """从首跳候选中确定唯一客户。

    Args:
        rows: 首跳客户查询返回的候选行。
        selection_context: 前端 wait-select 续跑时提交的选择上下文。
        trigger: 当前查询触发信息，用于判断强唯一线索。

    Returns:
        唯一客户行；如果仍需用户选择则返回 `None`。

    Edge Cases:
        - 强唯一线索也必须能在首跳结果中匹配到单行，否则仍进入候选选择，避免误绑。
        - `selection_context.user_select` 可以传 binding map，也可以传完整候选行，兼容前端不同绑定策略。
    """
    selected_from_context = _resolve_selected_customer_from_context(rows, selection_context)
    if selected_from_context is not None:
        return selected_from_context
    if len(rows) == 1:
        return rows[0]
    if trigger.identifier_type in {"customer_id", "phone", "id_card"}:
        matched_rows = [row for row in rows if _row_matches_trigger(row, trigger)]
        if len(matched_rows) == 1:
            return matched_rows[0]
    return None


def build_section_params(entry: ApiCatalogEntry, selected_customer: dict[str, Any]) -> dict[str, Any]:
    """根据选定客户构造档案分区接口参数。

    Args:
        entry: 当前分区接口元数据。
        selected_customer: 已经唯一化的客户行。

    Returns:
        下游档案接口请求参数。

    Edge Cases:
        - 优先遵守 Excel 中的 predecessor_specs；配置缺失时回退到 `encryptedIdCard`，保证旧元数据仍可用。
        - 固定分支永远绑定单个客户行，不使用 `[*]`，避免多客户扩散。
    """
    params: dict[str, Any] = {}
    for predecessor in entry.predecessors:
        if predecessor.predecessor_api_id != _CUSTOMER_LOOKUP_API_ID:
            continue
        for binding in predecessor.param_bindings:
            value = read_customer_value_by_source_path(selected_customer, binding.source_path)
            if value not in (None, ""):
                params[binding.target_param] = value

    if not params:
        encrypted_id_card = selected_customer.get("idCard") or selected_customer.get("encryptedIdCard")
        if encrypted_id_card not in (None, ""):
            params["encryptedIdCard"] = encrypted_id_card
    return params


def build_customer_profile_success_response(
    *,
    trace_id: str,
    query: str,
    trigger: CustomerProfileTrigger,
    selected_customer: dict[str, Any],
    plan: ApiQueryExecutionPlan,
    section_results: list[tuple[CustomerProfileSection, ApiCatalogEntry, ApiQueryExecutionResult, dict[str, Any]]],
) -> ApiQueryResponse:
    """构造固定客户档案成功响应。

    Args:
        trace_id: 当前链路追踪 ID。
        query: 原始用户问题，用于根卡片标题。
        trigger: 命中的固定分支触发信息。
        selected_customer: 已选定的客户行。
        plan: 固定 DAG 计划。
        section_results: 各档案分区的执行结果和请求参数。

    Returns:
        包含固定顺序 `PlannerDetailCard/PlannerInfoGrid/PlannerTable` 的 `ApiQueryResponse`。

    Edge Cases:
        单个分区失败不会移除该分区，而是保留错误占位，避免页面结构随接口稳定性漂移。
    """
    elements: dict[str, Any] = {}
    child_ids: list[str] = []
    has_error = False

    for section, entry, result, params in section_results:
        if result.status == ApiQueryExecutionStatus.ERROR:
            has_error = True
        child_ids.extend(
            build_section_elements(
                elements=elements,
                section=section,
                entry=entry,
                result=result,
                params=params,
                trace_id=trace_id,
            )
        )

    elements["root"] = {
        "type": "PlannerCard",
        "props": {
            "title": query,
            "subtitle": "客户健康档案 · 固定档案视图",
            "renderMode": _CUSTOMER_PROFILE_RENDER_MODE,
            "customer": {
                "name": selected_customer.get("name") or trigger.customer_value,
                "customerId": selected_customer.get("id") or selected_customer.get("customerId"),
                "encryptedIdCard": selected_customer.get("idCard") or selected_customer.get("encryptedIdCard"),
            },
        },
        "children": child_ids,
    }
    return ApiQueryResponse(
        trace_id=trace_id,
        execution_status=ApiQueryExecutionStatus.PARTIAL_SUCCESS if has_error else ApiQueryExecutionStatus.SUCCESS,
        execution_plan=plan,
        ui_spec={"root": "root", "state": {}, "elements": elements},
        error="部分客户档案分区获取失败" if has_error else None,
    )


def build_wait_select_response(
    *,
    trace_id: str,
    query: str,
    trigger: CustomerProfileTrigger,
    lookup_entry: ApiCatalogEntry,
    lookup_rows: list[dict[str, Any]],
    lookup_params: dict[str, Any],
    plan: ApiQueryExecutionPlan,
) -> ApiQueryResponse:
    """构造多客户候选等待选择响应。

    Args:
        trace_id: 当前链路追踪 ID。
        query: 原始用户问题，续跑时必须保留。
        trigger: 命中的固定分支触发信息。
        lookup_entry: 首跳客户查询接口元数据。
        lookup_rows: 首跳返回的候选客户列表。
        lookup_params: 首跳请求参数。
        plan: 当前只包含首跳的执行计划。

    Returns:
        `SKIPPED/WAIT_SELECT_REQUIRED` 响应，UI 中只包含候选客户表。

    Edge Cases:
        候选行会保留完整原始字段，同时额外放入 `bindingMap`，让前端既能展示消歧字段也能稳定续跑。
    """
    data_source = [build_candidate_row(row, index=index) for index, row in enumerate(lookup_rows, start=1)]
    columns = [
        {"key": field, "title": title, "dataIndex": field}
        for field, title in _CANDIDATE_TABLE_FIELDS
        if any(row.get(field) not in (None, "") for row in data_source)
    ]
    if not columns:
        columns = [{"key": "candidateIndex", "title": "候选序号", "dataIndex": "candidateIndex"}]

    table_id = "customer_candidates"
    elements = {
        "root": {
            "type": "PlannerCard",
            "props": {
                "title": f"请选择客户：{trigger.customer_value}",
                "subtitle": "命中多个客户，请先选择一个客户后继续展示档案。",
                "renderMode": "customer_profile_wait_select",
            },
            "children": [table_id],
        },
        table_id: {
            "type": "PlannerTable",
            "props": {
                "title": "候选客户",
                "columns": columns,
                "dataSource": data_source,
                "apiId": lookup_entry.id,
                "api": f"/api/v1/ui-builder/runtime/endpoints/{lookup_entry.id}/invoke",
                "queryParams": {},
                "body": dict(lookup_params),
                "flowNum": trace_id,
                "rowActions": [
                    {
                        "action": "remoteQuery",
                        "label": "使用该客户继续",
                        "params": {
                            "api": "/api/v1/api-query",
                            "queryParams": {},
                            "body": {
                                "query": query,
                                "selection_context": {"user_select": {"$bindRow": "bindingMap"}},
                            },
                        },
                    }
                ],
                "waitSelect": {
                    "pauseType": "WAIT_SELECT",
                    "selectionMode": "single",
                    "errorCode": "WAIT_SELECT_REQUIRED",
                },
            },
        },
    }
    return ApiQueryResponse(
        trace_id=trace_id,
        execution_status=ApiQueryExecutionStatus.SKIPPED,
        execution_plan=plan,
        ui_spec={"root": "root", "state": {}, "elements": elements},
        error="命中多个候选客户，请先选择后继续。",
    )


def build_customer_profile_error_response(
    *,
    trace_id: str,
    plan: ApiQueryExecutionPlan,
    title: str,
    message: str,
    status: ApiQueryExecutionStatus,
) -> ApiQueryResponse:
    """构造客户档案固定分支的终止响应。"""
    return ApiQueryResponse(
        trace_id=trace_id,
        execution_status=status,
        execution_plan=plan,
        ui_spec={
            "root": "root",
            "state": {},
            "elements": {
                "root": {
                    "type": "PlannerCard",
                    "props": {"title": title, "subtitle": "客户健康档案 · 固定档案视图"},
                    "children": ["notice"],
                },
                "notice": {"type": "PlannerNotice", "props": {"tone": "info", "text": message}},
            },
        },
        error=message,
    )


def build_section_elements(
    *,
    elements: dict[str, Any],
    section: CustomerProfileSection,
    entry: ApiCatalogEntry,
    result: ApiQueryExecutionResult,
    params: dict[str, Any],
    trace_id: str,
) -> list[str]:
    """把单个档案分区执行结果转换成 UI 元素。

    Args:
        elements: 正在组装的 flat spec 元素池。
        section: 当前固定展示分区。
        entry: 分区接口元数据。
        result: 该接口执行结果。
        params: 该接口的实际请求参数。
        trace_id: 当前链路追踪 ID。

    Returns:
        当前分区新增的元素 ID 列表。

    Edge Cases:
        资产分区是一个接口返回三块业务数据，因此拆成 `PlannerInfoGrid + 两个 PlannerTable`。
    """
    if section.key == "asset_overview":
        return build_asset_section_elements(elements, section=section, entry=entry, result=result, params=params, trace_id=trace_id)

    element_id = f"section_{section.key}"
    if result.status == ApiQueryExecutionStatus.ERROR:
        elements[element_id] = build_error_detail_card(section, entry, result)
        return [element_id]

    row = first_result_row(result.data)
    elements[element_id] = {
        "type": "PlannerDetailCard",
        "props": {
            "title": section.title,
            "bizFieldKey": section.key,
            "apiId": entry.id,
            "status": result.status.value,
            "items": build_detail_items(entry, row),
            **runtime_invoke_props(entry, params=params, trace_id=trace_id),
        },
    }
    return [element_id]


def build_asset_section_elements(
    elements: dict[str, Any],
    *,
    section: CustomerProfileSection,
    entry: ApiCatalogEntry,
    result: ApiQueryExecutionResult,
    params: dict[str, Any],
    trace_id: str,
) -> list[str]:
    """构造资产组合区元素。"""
    if result.status == ApiQueryExecutionStatus.ERROR:
        element_id = f"section_{section.key}"
        elements[element_id] = build_error_detail_card(section, entry, result)
        return [element_id]

    payload = first_result_row(result.data)
    summary = payload.get("summaryCard") if isinstance(payload.get("summaryCard"), dict) else {}
    delivery_records = payload.get("deliveryRecords") if isinstance(payload.get("deliveryRecords"), list) else []
    cure_plan_records = payload.get("curePlanRecords") if isinstance(payload.get("curePlanRecords"), list) else []
    label_index = extract_field_labels(entry.response_schema)

    summary_id = "section_asset_summary"
    delivery_id = "section_asset_delivery_records"
    cure_plan_id = "section_asset_cure_plan_records"
    elements[summary_id] = {
        "type": "PlannerInfoGrid",
        "props": {
            "title": "资产概览",
            "bizFieldKey": "summaryCard",
            "apiId": entry.id,
            "items": [
                {"label": label_index.get(field, field), "value": stringify_value(value)}
                for field, value in summary.items()
            ] or [{"label": "提示", "value": "暂无数据"}],
            **runtime_invoke_props(entry, params=params, trace_id=trace_id),
        },
    }
    elements[delivery_id] = build_table_element(
        title="历史购买储值方案",
        biz_field_key="deliveryRecords",
        api_id=entry.id,
        rows=normalize_result_rows(delivery_records),
        label_index=label_index,
        runtime_props=runtime_invoke_props(entry, params=params, trace_id=trace_id),
    )
    elements[cure_plan_id] = build_table_element(
        title="规划方案",
        biz_field_key="curePlanRecords",
        api_id=entry.id,
        rows=normalize_result_rows(cure_plan_records),
        label_index=label_index,
        runtime_props=runtime_invoke_props(entry, params=params, trace_id=trace_id),
    )
    return [summary_id, delivery_id, cure_plan_id]


def build_detail_items(entry: ApiCatalogEntry, row: dict[str, Any]) -> list[dict[str, str]]:
    """按详情元数据生成 `PlannerDetailCard.items`。"""
    label_index = extract_field_labels(entry.response_schema)
    fields = select_detail_fields(entry, row)
    if not fields:
        return [{"label": "提示", "value": "暂无数据"}]
    return [
        {"label": label_index.get(field, field), "value": stringify_value(row.get(field))}
        for field in fields
    ]


def select_detail_fields(entry: ApiCatalogEntry, row: dict[str, Any]) -> list[str]:
    """选择详情卡字段集合。"""
    display_fields = [field for field in entry.detail_view_meta.display_fields if field not in entry.detail_view_meta.exclude_fields]
    required_fields = [field for field in entry.detail_view_meta.required_fields if field not in entry.detail_view_meta.exclude_fields]
    ordered_fields = list(dict.fromkeys([*required_fields, *display_fields]))
    if ordered_fields:
        return ordered_fields
    return [field for field in row if field not in entry.detail_view_meta.exclude_fields]


def build_table_element(
    *,
    title: str,
    biz_field_key: str,
    api_id: str,
    rows: list[dict[str, Any]],
    label_index: dict[str, str],
    runtime_props: dict[str, Any],
) -> dict[str, Any]:
    """构造固定资产明细表。"""
    keys = list(rows[0].keys()) if rows else []
    return {
        "type": "PlannerTable",
        "props": {
            "title": title,
            "bizFieldKey": biz_field_key,
            "apiId": api_id,
            "columns": [
                {"key": key, "title": label_index.get(key, key), "dataIndex": key}
                for key in keys
            ],
            "dataSource": rows,
            **runtime_props,
        },
    }


def build_error_detail_card(
    section: CustomerProfileSection,
    entry: ApiCatalogEntry,
    result: ApiQueryExecutionResult,
) -> dict[str, Any]:
    """构造失败分区占位卡。"""
    return {
        "type": "PlannerDetailCard",
        "props": {
            "title": section.title,
            "bizFieldKey": section.key,
            "apiId": entry.id,
            "status": ApiQueryExecutionStatus.ERROR.value,
            "items": [{"label": "提示", "value": "该分区数据暂时获取失败"}],
            "error": {"message": result.error or "业务接口调用失败", "recoverable": bool(result.retryable)},
        },
    }


def runtime_invoke_props(entry: ApiCatalogEntry, *, params: dict[str, Any], trace_id: str) -> dict[str, Any]:
    """生成固定分区的 runtime invoke 元数据。"""
    return {
        "api": f"/api/v1/ui-builder/runtime/endpoints/{entry.id}/invoke",
        "queryParams": {} if entry.method == "POST" else dict(params),
        "body": dict(params) if entry.method == "POST" else {},
        "flowNum": trace_id,
    }


def build_candidate_row(row: dict[str, Any], *, index: int) -> dict[str, Any]:
    """构造候选客户表行，保留完整原始字段并补充续跑绑定。"""
    encrypted_id_card = row.get("idCard") or row.get("encryptedIdCard") or row.get("idcardCode")
    binding_key = f"{_CUSTOMER_LOOKUP_API_ID}:encryptedIdCard:idCard"
    return {
        **row,
        "candidateIndex": index,
        "candidateValue": encrypted_id_card or row.get("id") or row.get("customerId"),
        "bindingMap": {binding_key: encrypted_id_card, "customerRow": row},
    }


def normalize_result_rows(data: Any) -> list[dict[str, Any]]:
    """把接口结果统一为行列表。"""
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    if isinstance(data, dict):
        return [data]
    return []


def first_result_row(data: Any) -> dict[str, Any]:
    """读取详情型结果的第一条业务对象。"""
    rows = normalize_result_rows(data)
    return rows[0] if rows else {}


def read_customer_value_by_source_path(row: dict[str, Any], source_path: str) -> Any:
    """按 predecessor source_path 从选定客户行取值。"""
    path = source_path.strip()
    for prefix in ("$.", "$.data.", "$.data[*]."):
        if path.startswith(prefix):
            path = path[len(prefix):]
            break
    path = path.replace("[*]", "")
    current: Any = row
    for segment in [item for item in path.split(".") if item]:
        if not isinstance(current, dict):
            return None
        current = current.get(segment)
    return current


def parse_predecessor_specs(raw_value: Any) -> list[ApiCatalogPredecessorSpec]:
    """解析 Excel 中的 predecessor_specs。"""
    payload = load_json_value(raw_value, [])
    if not isinstance(payload, list):
        return []
    specs: list[ApiCatalogPredecessorSpec] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        bindings = []
        for binding in item.get("param_bindings") or []:
            if not isinstance(binding, dict):
                continue
            target_param = str(binding.get("target_param") or "").strip()
            source_path = str(binding.get("source_path") or "").strip()
            if not target_param or not source_path:
                continue
            select_mode = str(binding.get("select_mode") or "single").strip()
            if select_mode not in {"single", "first", "user_select", "all"}:
                select_mode = "single"
            bindings.append(
                ApiCatalogPredecessorParamBinding(
                    target_param=target_param,
                    source_path=source_path,
                    select_mode=select_mode,  # type: ignore[arg-type]
                )
            )
        predecessor_api_id = str(item.get("predecessor_api_id") or "").strip()
        if not predecessor_api_id:
            continue
        specs.append(
            ApiCatalogPredecessorSpec(
                predecessor_api_id=predecessor_api_id,
                required=bool(item.get("required", True)),
                order=int(item.get("order") or 100),
                param_bindings=bindings,
            )
        )
    return sorted(specs, key=lambda spec: (spec.order, spec.predecessor_api_id))


def parse_detail_view_meta(raw_value: Any) -> ApiCatalogDetailViewMeta:
    """解析 Excel 中的详情展示元数据。"""
    payload = load_json_value(raw_value, {})
    if not isinstance(payload, dict):
        return ApiCatalogDetailViewMeta()
    try:
        return ApiCatalogDetailViewMeta.model_validate(payload)
    except Exception:
        return ApiCatalogDetailViewMeta()


def to_param_schema(value: dict[str, Any]) -> ParamSchema:
    """把 JSON Schema 压缩成执行目录使用的参数 schema。"""
    if not isinstance(value, dict):
        return ParamSchema()
    try:
        return ParamSchema.model_validate(value)
    except Exception:
        return ParamSchema()


def infer_response_data_path(response_schema: dict[str, Any]) -> str:
    """推断执行器需要的响应数据路径。"""
    properties = response_schema.get("properties") if isinstance(response_schema, dict) else None
    if not isinstance(properties, dict):
        return "data"
    result_property = properties.get("result")
    if isinstance(result_property, dict):
        result_properties = result_property.get("properties")
        if isinstance(result_properties, dict):
            if isinstance(result_properties.get("records"), dict):
                return "result.records"
            if isinstance(result_properties.get("list"), dict):
                return "result.list"
            return "result"
    data_property = properties.get("data")
    if isinstance(data_property, dict):
        data_properties = data_property.get("properties")
        if isinstance(data_properties, dict):
            if isinstance(data_properties.get("records"), dict):
                return "data.records"
            if isinstance(data_properties.get("list"), dict):
                return "data.list"
            return "data"
    return "data"


def extract_field_labels(response_schema: dict[str, Any]) -> dict[str, str]:
    """从响应 schema 提取字段中文名。"""
    labels: dict[str, str] = {}

    def collect(properties: dict[str, Any]) -> None:
        for name, schema in properties.items():
            if not isinstance(schema, dict):
                continue
            label = schema.get("description") or schema.get("title")
            if isinstance(label, str) and label.strip():
                labels.setdefault(name, label.strip())

            # 资产接口存在 summaryCard / records[] 等嵌套结构；递归收集能保证表格列仍使用业务 description。
            nested_properties = schema.get("properties")
            if isinstance(nested_properties, dict):
                collect(nested_properties)
            items = schema.get("items")
            item_properties = items.get("properties") if isinstance(items, dict) else None
            if isinstance(item_properties, dict):
                collect(item_properties)

    collect(schema_property_candidates(response_schema))
    return labels


def schema_property_candidates(response_schema: dict[str, Any]) -> dict[str, Any]:
    """定位响应 schema 中最接近业务字段的一层 properties。"""
    properties = response_schema.get("properties") if isinstance(response_schema, dict) else None
    if not isinstance(properties, dict):
        return {}
    for container_name in ("result", "data"):
        container = properties.get(container_name)
        if not isinstance(container, dict):
            continue
        container_props = container.get("properties")
        if not isinstance(container_props, dict):
            continue
        for list_name in ("records", "list"):
            list_schema = container_props.get(list_name)
            if isinstance(list_schema, dict):
                items = list_schema.get("items")
                item_props = items.get("properties") if isinstance(items, dict) else None
                if isinstance(item_props, dict):
                    return item_props
        return container_props
    return properties


def stringify_value(value: Any) -> str:
    """把详情值转换成稳定展示文本。"""
    if value in (None, ""):
        return "-"
    if isinstance(value, list):
        if not value:
            return "-"
        if all(not isinstance(item, dict) for item in value):
            return "、".join(str(item) for item in value if item not in (None, "")) or "-"
        return f"共 {len(value)} 条记录"
    if isinstance(value, dict):
        return "-" if not value else "已记录"
    return str(value)


def _resolve_selected_customer_from_context(
    rows: list[dict[str, Any]],
    selection_context: dict[str, Any] | None,
) -> dict[str, Any] | None:
    selected = selection_context.get("user_select") if isinstance(selection_context, dict) else None
    if not isinstance(selected, dict):
        return None
    customer_row = selected.get("customerRow")
    if isinstance(customer_row, dict):
        return dict(customer_row)
    candidate_values = [value for value in selected.values() if value not in (None, "") and not isinstance(value, dict)]
    for row in rows:
        row_values = {str(value) for value in row.values() if value not in (None, "")}
        if any(str(value) in row_values for value in candidate_values):
            return row
    return None


def _row_matches_trigger(row: dict[str, Any], trigger: CustomerProfileTrigger) -> bool:
    target = trigger.customer_value
    if trigger.identifier_type == "customer_id":
        return target in {str(row.get("id") or ""), str(row.get("customerId") or ""), str(row.get("customerMasterId") or "")}
    if trigger.identifier_type == "phone":
        return target in {str(row.get("phone") or ""), str(row.get("phoneObfuscated") or "")}
    if trigger.identifier_type == "id_card":
        return target in {str(row.get("idCard") or ""), str(row.get("idCardObfuscated") or "")}
    return False


def _clean_customer_name(value: str) -> str:
    cleaned = value.strip(" 的，。；;:：")
    # “怎么维护客户信息”这类知识问答不包含具体客户，必须留给通用链路而不是误触发档案页。
    if any(keyword in cleaned for keyword in ("怎么", "如何", "维护", "配置", "管理", "字段", "接口", "页面")):
        return ""
    for keyword in _PROFILE_KEYWORDS:
        cleaned = cleaned.replace(keyword, "")
    return cleaned.strip(" 的，。；;:：")


def _normalize_operation_safety(value: str) -> str:
    return "mutation" if value == "mutation" else "query"


def _normalize_method(value: str) -> str:
    method = (value or "GET").strip().upper()
    return method if method in {"GET", "POST", "PUT", "DELETE", "PATCH"} else "GET"


def _cell(row: list[Any], index: dict[str, int], name: str) -> str:
    position = index.get(name)
    if position is None or position >= len(row):
        return ""
    value = row[position]
    return "" if value is None else str(value).strip()


def _read_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    try:
        payload = archive.read("xl/sharedStrings.xml")
    except KeyError:
        return []
    root = ElementTree.fromstring(payload)
    values: list[str] = []
    for item in root.findall("main:si", _XLSX_NS):
        texts = [node.text or "" for node in item.findall(".//main:t", _XLSX_NS)]
        values.append(unescape("".join(texts)))
    return values


def _resolve_sheet_path(archive: zipfile.ZipFile, relationship_id: str | None) -> str:
    if not relationship_id:
        return "xl/worksheets/sheet1.xml"
    rels = ElementTree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    for rel in rels.findall("pkg:Relationship", _XLSX_NS):
        if rel.attrib.get("Id") != relationship_id:
            continue
        target = rel.attrib.get("Target", "worksheets/sheet1.xml")
        return f"xl/{target}" if not target.startswith("/") and not target.startswith("xl/") else target.lstrip("/")
    return "xl/worksheets/sheet1.xml"


def _read_cell_value(cell: ElementTree.Element, shared_strings: list[str]) -> Any:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        texts = [node.text or "" for node in cell.findall(".//main:t", _XLSX_NS)]
        return unescape("".join(texts))

    value_node = cell.find("main:v", _XLSX_NS)
    if value_node is None or value_node.text is None:
        return None
    raw_value = value_node.text
    if cell_type == "s":
        try:
            return shared_strings[int(raw_value)]
        except (IndexError, ValueError):
            return ""
    if cell_type == "b":
        return raw_value == "1"
    return raw_value


def _column_index_from_ref(cell_ref: str) -> int:
    column = "".join(ch for ch in cell_ref if ch.isalpha())
    if not column:
        return -1
    index = 0
    for char in column.upper():
        index = index * 26 + (ord(char) - ord("A") + 1)
    return index - 1
