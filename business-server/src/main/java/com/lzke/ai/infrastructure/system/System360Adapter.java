package com.lzke.ai.infrastructure.system;

import org.springframework.stereotype.Component;

import java.util.HashMap;
import java.util.Map;

/**
 * 360系统适配器 — 对接360综合管理系统。
 */
@Component
public class System360Adapter extends BaseSystemAdapter {

    @Override
    public String getSystemCode() { return "system360"; }

    @Override
    public String getSystemName() { return "360系统"; }

    @Override
    protected Map<String, Object> mapTaskFields(Map<String, Object> raw) {
        Map<String, Object> mapped = new HashMap<>();
        mapped.put("sourceId", firstNonNull(raw, "record_id", "item_id", "id"));
        mapped.put("title", firstNonNull(raw, "item_title", "name", "title"));
        mapped.put("description", firstNonNull(raw, "content", "description"));
        mapped.put("status", mapStatus(String.valueOf(firstNonNull(raw, "state", "status"))));
        mapped.put("priority", mapPriority(String.valueOf(firstNonNull(raw, "priority", "level"))));
        mapped.put("deadline", firstNonNull(raw, "expire_time", "deadline"));
        mapped.put("externalUrl", firstNonNull(raw, "jump_url", "url"));
        return mapped;
    }

    @Override
    protected Map<String, Object> mapActionResponse(Map<String, Object> raw) {
        Map<String, Object> mapped = new HashMap<>();
        mapped.put("result", firstNonNull(raw, "ret", "result", "code"));
        mapped.put("message", firstNonNull(raw, "errmsg", "message", "msg"));
        mapped.put("data", raw.get("data"));
        return mapped;
    }

    private String mapStatus(String status) {
        if (status == null) return "pending";
        return switch (status) {
            case "待处理", "0", "pending" -> "pending";
            case "进行中", "1", "processing" -> "in_progress";
            case "已完成", "2", "done" -> "completed";
            default -> "pending";
        };
    }

    private String mapPriority(String priority) {
        if (priority == null) return "normal";
        return switch (priority) {
            case "紧急", "critical" -> "urgent";
            case "高", "high" -> "high";
            case "低", "low" -> "low";
            default -> "normal";
        };
    }

    private Object firstNonNull(Map<String, Object> map, String... keys) {
        for (String key : keys) {
            Object val = map.get(key);
            if (val != null) return val;
        }
        return null;
    }
}
