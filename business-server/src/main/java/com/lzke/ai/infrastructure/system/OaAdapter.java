package com.lzke.ai.infrastructure.system;

import org.springframework.stereotype.Component;

import java.util.HashMap;
import java.util.Map;

/**
 * OA系统适配器
 * <p>
 * 对接办公自动化系统，拉取请假审批、公文流转、会议安排等待办任务。
 * <p>
 * OA系统典型字段映射：
 * - flow_id / process_id   → sourceId
 * - flow_title / subject   → title
 * - flow_status / state    → status
 * - urgent_level           → priority
 * - flow_url / link        → externalUrl
 * - expire_time            → deadline
 * - content / abstract     → description
 */
@Component
public class OaAdapter extends BaseSystemAdapter {

    @Override
    public String getSystemCode() {
        return "oa";
    }

    @Override
    public String getSystemName() {
        return "OA";
    }

    @Override
    protected Map<String, Object> mapTaskFields(Map<String, Object> raw) {
        Map<String, Object> mapped = new HashMap<>();

        // sourceId: 优先取 flow_id，其次 process_id，最后 id
        mapped.put("sourceId", coalesce(raw, "flow_id", "process_id", "id"));

        // title: 优先取 flow_title，其次 subject，最后 title
        mapped.put("title", coalesce(raw, "flow_title", "subject", "title"));

        // status: 映射OA系统状态到标准状态
        mapped.put("status", mapOaStatus(getString(raw, "flow_status", "state", "status")));

        // priority: 映射OA优先级
        mapped.put("priority", mapOaPriority(getString(raw, "urgent_level", "priority")));

        // externalUrl
        mapped.put("externalUrl", coalesce(raw, "flow_url", "link", "externalUrl", "url"));

        // deadline
        mapped.put("deadline", coalesce(raw, "expire_time", "deadline", "due_date"));

        // description
        mapped.put("description", coalesce(raw, "content", "abstract", "description"));

        return mapped;
    }

    @Override
    protected Map<String, Object> mapActionResponse(Map<String, Object> raw) {
        Map<String, Object> result = new HashMap<>();
        // OA系统通常返回 code + msg 格式
        Object code = raw.getOrDefault("code", raw.get("status"));
        boolean success = "0".equals(String.valueOf(code)) || "200".equals(String.valueOf(code))
                || "success".equalsIgnoreCase(String.valueOf(code));
        result.put("status", success ? "success" : "error");
        result.put("message", raw.getOrDefault("msg", raw.getOrDefault("message", "")));
        result.put("data", raw.get("data"));
        return result;
    }

    // ==================== OA特有映射逻辑 ====================

    /**
     * OA状态映射：将OA系统的流程状态转为标准任务状态
     */
    private String mapOaStatus(String oaStatus) {
        if (oaStatus == null) return "pending";
        return switch (oaStatus.toLowerCase()) {
            case "待审批", "待处理", "pending", "draft", "submitted" -> "pending";
            case "审批中", "流转中", "processing", "in_progress", "running" -> "in_progress";
            case "已通过", "已完成", "approved", "completed", "finished" -> "completed";
            case "已驳回", "rejected", "denied", "refused" -> "rejected";
            case "已撤回", "已终止", "withdrawn", "terminated", "cancelled" -> "cancelled";
            default -> "pending";
        };
    }

    /**
     * OA优先级映射
     */
    private String mapOaPriority(String oaPriority) {
        if (oaPriority == null) return "normal";
        return switch (oaPriority.toLowerCase()) {
            case "特急", "加急", "urgent", "1" -> "urgent";
            case "紧急", "high", "2" -> "high";
            case "普通", "normal", "3" -> "normal";
            case "一般", "low", "4" -> "low";
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
