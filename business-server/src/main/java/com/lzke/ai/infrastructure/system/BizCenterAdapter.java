package com.lzke.ai.infrastructure.system;

import org.springframework.stereotype.Component;

import java.util.HashMap;
import java.util.Map;

/**
 * 业务中台适配器 — 对接内部业务中台系统。
 */
@Component
public class BizCenterAdapter extends BaseSystemAdapter {

    @Override
    public String getSystemCode() { return "biz_center"; }

    @Override
    public String getSystemName() { return "业务中台"; }

    @Override
    protected Map<String, Object> mapTaskFields(Map<String, Object> raw) {
        Map<String, Object> mapped = new HashMap<>();
        mapped.put("sourceId", coalesce(raw, "task_id", "biz_id", "id"));
        mapped.put("title", coalesce(raw, "task_name", "title"));
        mapped.put("description", coalesce(raw, "detail", "description"));
        mapped.put("status", mapStatus(String.valueOf(coalesce(raw, "task_status", "status"))));
        mapped.put("priority", mapPriority(String.valueOf(coalesce(raw, "priority", "level"))));
        mapped.put("deadline", coalesce(raw, "due_date", "deadline"));
        mapped.put("externalUrl", coalesce(raw, "link", "url"));
        return mapped;
    }

    @Override
    protected Map<String, Object> mapActionResponse(Map<String, Object> raw) {
        Map<String, Object> mapped = new HashMap<>();
        mapped.put("result", coalesce(raw, "result", "code"));
        mapped.put("message", coalesce(raw, "message", "msg"));
        mapped.put("data", raw.get("data"));
        return mapped;
    }

    private String mapStatus(String status) {
        if (status == null) return "pending";
        return switch (status) {
            case "待处理", "new", "pending" -> "pending";
            case "处理中", "processing", "in_progress" -> "in_progress";
            case "已完成", "done", "completed" -> "completed";
            default -> "pending";
        };
    }

    private String mapPriority(String priority) {
        if (priority == null) return "normal";
        return switch (priority) {
            case "紧急", "urgent", "P0" -> "urgent";
            case "高", "high", "P1" -> "high";
            case "低", "low", "P3" -> "low";
            default -> "normal";
        };
    }
}
