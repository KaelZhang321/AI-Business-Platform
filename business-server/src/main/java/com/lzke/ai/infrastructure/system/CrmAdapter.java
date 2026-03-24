package com.lzke.ai.infrastructure.system;

import org.springframework.stereotype.Component;

import java.util.HashMap;
import java.util.Map;

/**
 * CRM系统适配器
 * <p>
 * 对接客户关系管理系统，拉取客户跟进、商机推进、合同审批等待办任务。
 * <p>
 * CRM系统典型字段映射：
 * - opportunity_id / lead_id  → sourceId
 * - task_name / name          → title
 * - stage / task_status       → status
 * - importance / priority     → priority
 * - link / detail_link        → externalUrl
 * - follow_up_date            → deadline
 * - notes / summary           → description
 */
@Component
public class CrmAdapter extends BaseSystemAdapter {

    @Override
    public String getSystemCode() {
        return "crm";
    }

    @Override
    public String getSystemName() {
        return "CRM";
    }

    @Override
    protected Map<String, Object> mapTaskFields(Map<String, Object> raw) {
        Map<String, Object> mapped = new HashMap<>();

        // sourceId: 优先取 opportunity_id，其次 lead_id，最后 id
        mapped.put("sourceId", coalesce(raw, "opportunity_id", "lead_id", "id"));

        // title: 优先取 task_name，其次 name，最后 title
        mapped.put("title", coalesce(raw, "task_name", "name", "title"));

        // status: 映射CRM系统状态到标准状态
        mapped.put("status", mapCrmStatus(getString(raw, "stage", "task_status", "status")));

        // priority: 映射CRM优先级
        mapped.put("priority", mapCrmPriority(getString(raw, "importance", "priority")));

        // externalUrl
        mapped.put("externalUrl", coalesce(raw, "link", "detail_link", "externalUrl", "url"));

        // deadline
        mapped.put("deadline", coalesce(raw, "follow_up_date", "due_date", "deadline"));

        // description
        mapped.put("description", coalesce(raw, "notes", "summary", "description"));

        return mapped;
    }

    @Override
    protected Map<String, Object> mapActionResponse(Map<String, Object> raw) {
        Map<String, Object> result = new HashMap<>();
        result.put("status", raw.getOrDefault("success", false).equals(true) ? "success" :
                raw.getOrDefault("status", "unknown"));
        result.put("message", raw.getOrDefault("message", raw.getOrDefault("error", "")));
        result.put("data", raw.get("data"));
        return result;
    }

    // ==================== CRM特有映射逻辑 ====================

    /**
     * CRM状态映射：将CRM系统的商机/线索阶段转为标准任务状态
     */
    private String mapCrmStatus(String crmStatus) {
        if (crmStatus == null) return "pending";
        return switch (crmStatus.toLowerCase()) {
            case "新线索", "new_lead", "new", "待跟进" -> "pending";
            case "跟进中", "following", "in_progress", "negotiation" -> "in_progress";
            case "已成交", "won", "closed_won", "completed" -> "completed";
            case "已流失", "lost", "closed_lost" -> "rejected";
            case "已暂停", "on_hold", "suspended" -> "cancelled";
            default -> "pending";
        };
    }

    /**
     * CRM优先级映射
     */
    private String mapCrmPriority(String crmPriority) {
        if (crmPriority == null) return "normal";
        return switch (crmPriority.toLowerCase()) {
            case "紧急", "critical", "p0" -> "urgent";
            case "重要", "high", "important", "p1" -> "high";
            case "普通", "normal", "medium", "p2" -> "normal";
            case "较低", "low", "p3" -> "low";
            default -> "normal";
        };
    }

}
