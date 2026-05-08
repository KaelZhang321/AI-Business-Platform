package com.lzke.ai.service;

import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;

/**
 * 审计日志统计分析服务 — 基于 ClickHouse 的聚合查询。
 */
@Slf4j
@Service
public class AnalyticsService {

    private final JdbcTemplate clickHouseJdbc;

    public AnalyticsService(@Qualifier("clickHouseJdbcTemplate") ObjectProvider<JdbcTemplate> clickHouseJdbcProvider) {
        this.clickHouseJdbc = clickHouseJdbcProvider.getIfAvailable();
        if (this.clickHouseJdbc == null) {
            log.info("ClickHouse analytics is disabled or unavailable; audit analytics endpoints will return empty results.");
        }
    }

    public List<Map<String, Object>> statsByIntent(String startDate, String endDate) {
        if (clickHouseJdbc == null) {
            return List.of();
        }
        String sql = """
                SELECT intent, count() AS total, avg(latency_ms) AS avg_latency,
                       sum(input_tokens) AS total_input_tokens, sum(output_tokens) AS total_output_tokens
                FROM audit_logs
                WHERE created_at >= ? AND created_at < ?
                GROUP BY intent
                ORDER BY total DESC
                """;
        return clickHouseJdbc.queryForList(sql, startDate, endDate);
    }

    public List<Map<String, Object>> statsByModel(String startDate, String endDate) {
        if (clickHouseJdbc == null) {
            return List.of();
        }
        String sql = """
                SELECT model, count() AS total, avg(latency_ms) AS avg_latency,
                       sum(input_tokens + output_tokens) AS total_tokens
                FROM audit_logs
                WHERE created_at >= ? AND created_at < ?
                GROUP BY model
                ORDER BY total DESC
                """;
        return clickHouseJdbc.queryForList(sql, startDate, endDate);
    }

    public List<Map<String, Object>> statsByHour(String date) {
        if (clickHouseJdbc == null) {
            return List.of();
        }
        String sql = """
                SELECT toHour(created_at) AS hour, count() AS total, avg(latency_ms) AS avg_latency
                FROM audit_logs
                WHERE toDate(created_at) = ?
                GROUP BY hour
                ORDER BY hour
                """;
        return clickHouseJdbc.queryForList(sql, date);
    }

    public void insertAuditLog(Map<String, Object> logData) {
        if (clickHouseJdbc == null) {
            return;
        }
        String sql = """
                INSERT INTO audit_logs (trace_id, user_id, intent, model, input_tokens, output_tokens, latency_ms, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, now())
                """;
        try {
            clickHouseJdbc.update(sql,
                    logData.get("traceId"),
                    logData.get("userId"),
                    logData.get("intent"),
                    logData.get("model"),
                    logData.getOrDefault("inputTokens", 0),
                    logData.getOrDefault("outputTokens", 0),
                    logData.getOrDefault("latencyMs", 0),
                    logData.getOrDefault("status", "success")
            );
        } catch (Exception e) {
            log.warn("ClickHouse 审计日志写入失败: {}", e.getMessage());
        }
    }
}
