"""API Query 第二阶段业务意图契约。

功能：
    集中维护第二阶段对外暴露的 canonical business intents，以及历史编码到新契约的兼容映射。
    这样 route 层、参数提取层和审计层共享同一份语义字典，避免“Prompt、白名单、响应对象”三处漂移。
"""

from __future__ import annotations


NOOP_BUSINESS_INTENT = "none"
LEGACY_READ_BUSINESS_INTENT_CODES = {
    "none",
    "query_business_data",
    "query_detail_data",
}

CANONICAL_BUSINESS_INTENTS: dict[str, dict[str, str]] = {
    "none": {
        "name": "纯查询",
        "category": "read",
        "description": "当前请求仅包含读取诉求，不携带写前确认意图。",
    },
    "saveToServer": {
        "name": "保存业务数据",
        "category": "write",
        "description": "用户希望保存、修改或写入业务数据，但不会在 api_query 中直接执行。",
    },
    "deleteCustomer": {
        "name": "删除客户数据",
        "category": "write",
        "description": "用户希望删除或废弃客户相关记录，但不会在 api_query 中直接执行。",
    },
}

BUSINESS_INTENT_ALIASES = {
    # 历史 Phase 02 使用“准备态”编码，这里保留兼容，避免线上 Prompt / catalog 混用时误降级成 none。
    "prepare_record_update": "saveToServer",
    "prepare_high_risk_change": "saveToServer",
    "update_contract_amount": "saveToServer",
    "delete_customer_record": "deleteCustomer",
}

HIGH_RISK_BUSINESS_INTENT_CODES = {"deleteCustomer"}
HIGH_RISK_BUSINESS_INTENT_ALIASES = {
    "prepare_high_risk_change",
    "update_contract_amount",
    "delete_customer_record",
}


def normalize_business_intent_code(raw_code: str | None) -> str:
    """将单个业务意图编码折叠成 canonical code。

    Args:
        raw_code: LLM、旧 Prompt 或历史 catalog 中出现的原始业务意图编码。

    Returns:
        对外稳定的 canonical business intent code；未知值原样返回，由上层白名单决定是否丢弃。

    Edge Cases:
        - 历史只读编码不会在这里直接变成 `none`，统一交给批量归一化逻辑做兜底
        - 未知编码不在此处猜测，避免把幻觉动作误判成真实写意图
    """
    normalized = (raw_code or "").strip()
    return BUSINESS_INTENT_ALIASES.get(normalized, normalized)


def normalize_business_intent_codes(raw_codes: list[str]) -> list[str]:
    """将一组业务意图折叠成设计文档约定的稳定集合。

    Args:
        raw_codes: 第二阶段原始业务意图编码列表，可能混入历史别名和旧只读编码。

    Returns:
        只包含 canonical write intents 的去重列表；若没有合法写意图，则返回 `["none"]`。

    Edge Cases:
        - 历史读意图统一折叠为 `none`
        - 非法编码在白名单过滤前不会被猜测修复，只会被丢弃
    """
    normalized_codes: list[str] = []
    for raw_code in raw_codes:
        canonical_code = normalize_business_intent_code(raw_code)
        if canonical_code in LEGACY_READ_BUSINESS_INTENT_CODES:
            continue
        if canonical_code in CANONICAL_BUSINESS_INTENTS:
            normalized_codes.append(canonical_code)

    write_codes = [code for code in normalized_codes if code not in LEGACY_READ_BUSINESS_INTENT_CODES]
    return list(dict.fromkeys(write_codes)) or [NOOP_BUSINESS_INTENT]


def resolve_business_intent_risk_level(code: str, raw_codes: list[str]) -> str | None:
    """根据 canonical code 与历史别名推导审计风险等级。

    Args:
        code: 已归一化后的 canonical business intent。
        raw_codes: 第二阶段产生的原始业务意图编码列表。

    Returns:
        `high` 或 `None`。当前只在确有高危删除 / 高危更新信号时返回高风险。

    Edge Cases:
        - 删除客户天然视为高风险
        - 历史高危更新别名会被折叠成 `saveToServer`，但风险等级不能丢
    """
    if code in HIGH_RISK_BUSINESS_INTENT_CODES:
        return "high"
    if any(raw_code in HIGH_RISK_BUSINESS_INTENT_ALIASES for raw_code in raw_codes):
        return "high"
    return None
