package com.lzke.ai.listener;

import com.lzke.ai.config.RabbitMQConfig;
import com.lzke.ai.domain.entity.AuditLog;
import com.lzke.ai.infrastructure.persistence.mapper.AuditLogMapper;
import com.lzke.ai.service.AnalyticsService;
import com.rabbitmq.client.Channel;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.amqp.rabbit.annotation.RabbitListener;
import org.springframework.amqp.support.AmqpHeaders;
import org.springframework.messaging.handler.annotation.Header;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.util.Map;

/**
 * 审计日志消费者 — 监听 audit.log 队列，双写 MySQL + ClickHouse。
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class AuditLogListener {

    private final AuditLogMapper auditLogMapper;
    private final AnalyticsService analyticsService;

    @RabbitListener(queues = RabbitMQConfig.AUDIT_LOG_QUEUE)
    public void onAuditLog(Map<String, Object> message, Channel channel,
                           @Header(AmqpHeaders.DELIVERY_TAG) long deliveryTag) throws IOException {
        try {
            AuditLog auditLog = new AuditLog();
            auditLog.setTraceId(getString(message, "traceId"));
            String userId = getString(message, "userId");
            if (userId != null && !userId.isEmpty()) {
                auditLog.setUserId(userId);
            }
            auditLog.setIntent(getString(message, "intent"));
            auditLog.setModel(getString(message, "model"));
            auditLog.setInputTokens(getInt(message, "inputTokens"));
            auditLog.setOutputTokens(getInt(message, "outputTokens"));
            auditLog.setLatencyMs(getInt(message, "latencyMs"));
            auditLog.setStatus(getString(message, "status", "success"));

            // 写入 MySQL
            auditLogMapper.insert(auditLog);
            log.debug("审计日志写入MySQL成功: traceId={}", auditLog.getTraceId());

            // 写入 ClickHouse (异步、容忍失败)
            analyticsService.insertAuditLog(message);

            channel.basicAck(deliveryTag, false);
        } catch (Exception e) {
            log.error("审计日志写入失败: {}", e.getMessage(), e);
            channel.basicNack(deliveryTag, false, true);
        }
    }

    private static String getString(Map<String, Object> map, String key) {
        return getString(map, key, null);
    }

    private static String getString(Map<String, Object> map, String key, String defaultValue) {
        Object val = map.get(key);
        return val != null ? val.toString() : defaultValue;
    }

    private static int getInt(Map<String, Object> map, String key) {
        Object val = map.get(key);
        if (val instanceof Number n) return n.intValue();
        if (val != null) {
            try { return Integer.parseInt(val.toString()); } catch (NumberFormatException ignored) {}
        }
        return 0;
    }
}
