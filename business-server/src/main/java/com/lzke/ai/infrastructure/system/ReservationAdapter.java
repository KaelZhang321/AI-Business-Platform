package com.lzke.ai.infrastructure.system;

import org.springframework.stereotype.Component;

import java.util.HashMap;
import java.util.Map;

/**
 * 预约系统适配器 — 对接预约系统获取待办和操作。
 */
@Component
public class ReservationAdapter extends BaseSystemAdapter {

    @Override
    public String getSystemCode() { return "reservation"; }

    @Override
    public String getSystemName() { return "预约系统"; }

    @Override
    protected Map<String, Object> mapTaskFields(Map<String, Object> raw) {
        Map<String, Object> mapped = new HashMap<>();
        mapped.put("sourceId", coalesce(raw, "reservation_id", "booking_id", "id"));
        mapped.put("title", coalesce(raw, "service_name", "title", "subject"));
        mapped.put("description", coalesce(raw, "customer_name", "description", "remark"));
        mapped.put("status", mapStatus(String.valueOf(coalesce(raw, "booking_status", "status"))));
        mapped.put("priority", mapPriority(String.valueOf(coalesce(raw, "urgency", "priority"))));
        mapped.put("deadline", coalesce(raw, "appointment_time", "scheduled_at", "deadline"));
        mapped.put("externalUrl", coalesce(raw, "detail_url", "url"));
        return mapped;
    }

    @Override
    protected Map<String, Object> mapActionResponse(Map<String, Object> raw) {
        Map<String, Object> mapped = new HashMap<>();
        mapped.put("result", coalesce(raw, "result", "status"));
        mapped.put("message", coalesce(raw, "message", "msg"));
        mapped.put("data", raw.get("data"));
        return mapped;
    }

    private String mapStatus(String status) {
        if (status == null) return "pending";
        return switch (status) {
            case "待确认", "pending" -> "pending";
            case "已确认", "confirmed", "处理中" -> "in_progress";
            case "已完成", "completed" -> "completed";
            case "已取消", "cancelled" -> "cancelled";
            default -> "pending";
        };
    }

    private String mapPriority(String priority) {
        if (priority == null) return "normal";
        return switch (priority) {
            case "紧急", "urgent" -> "urgent";
            case "高", "high" -> "high";
            case "低", "low" -> "low";
            default -> "normal";
        };
    }
}
