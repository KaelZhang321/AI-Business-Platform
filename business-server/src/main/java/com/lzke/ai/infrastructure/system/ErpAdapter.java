package com.lzke.ai.infrastructure.system;

import org.springframework.stereotype.Component;

import java.util.HashMap;
import java.util.Map;

/**
 * ERP系统适配器
 * <p>
 * 对接企业资源规划系统，拉取采购审批、库存预警、财务报销等待办任务。
 * <p>
 * ERP系统典型字段映射：
 * - order_no / orderNumber → sourceId
 * - subject / title       → title
 * - order_status           → status
 * - urgency / level        → priority
 * - detail_url             → externalUrl
 * - due_date               → deadline
 * - remark / description   → description
 */
@Component
public class ErpAdapter extends BaseSystemAdapter {

    @Override
    public String getSystemCode() {
        return "erp";
    }

    @Override
    public String getSystemName() {
        return "ERP";
    }

    @Override
    protected Map<String, Object> mapTaskFields(Map<String, Object> raw) {
        Map<String, Object> mapped = new HashMap<>();

        // sourceId: 优先取 order_no，其次 orderNumber，最后 id
        mapped.put("sourceId", coalesce(raw, "order_no", "orderNumber", "id"));

        // title: 优先取 subject，其次 title
        mapped.put("title", coalesce(raw, "subject", "title"));

        // status: 映射ERP系统状态到标准状态
        mapped.put("status", mapErpStatus(getString(raw, "order_status", "status")));

        // priority: 映射ERP系统优先级
        mapped.put("priority", mapErpPriority(getString(raw, "urgency", "level", "priority")));

        // externalUrl
        mapped.put("externalUrl", coalesce(raw, "detail_url", "externalUrl", "url"));

        // deadline
        mapped.put("deadline", coalesce(raw, "due_date", "deadline"));

        // description
        mapped.put("description", coalesce(raw, "remark", "description"));

        return mapped;
    }

    @Override
    protected Map<String, Object> mapActionResponse(Map<String, Object> raw) {
        Map<String, Object> result = new HashMap<>();
        result.put("status", raw.getOrDefault("result", raw.getOrDefault("status", "unknown")));
        result.put("message", raw.getOrDefault("message", raw.getOrDefault("msg", "")));
        result.put("data", raw.get("data"));
        return result;
    }

    // ==================== ERP特有映射逻辑 ====================

    /**
     * ERP状态映射：将ERP系统特有状态转为标准状态
     */
    private String mapErpStatus(String erpStatus) {
        if (erpStatus == null) return "pending";
        return switch (erpStatus.toLowerCase()) {
            case "待审批", "pending_approval", "submitted" -> "pending";
            case "处理中", "processing", "in_progress" -> "in_progress";
            case "已完成", "completed", "approved" -> "completed";
            case "已拒绝", "rejected", "denied" -> "rejected";
            case "已取消", "cancelled", "canceled" -> "cancelled";
            default -> "pending";
        };
    }

    /**
     * ERP优先级映射
     */
    private String mapErpPriority(String erpPriority) {
        if (erpPriority == null) return "normal";
        return switch (erpPriority.toLowerCase()) {
            case "紧急", "urgent", "critical", "1" -> "urgent";
            case "高", "high", "2" -> "high";
            case "普通", "normal", "medium", "3" -> "normal";
            case "低", "low", "4" -> "low";
            default -> "normal";
        };
    }

    // ==================== 工具方法 ====================

    private Object coalesce(Map<String, Object> map, String... keys) {
        for (String key : keys) {
            Object val = map.get(key);
            if (val != null) return val;
        }
        return null;
    }

    private String getString(Map<String, Object> map, String... keys) {
        Object val = coalesce(map, keys);
        return val != null ? val.toString() : null;
    }
}
