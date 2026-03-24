package com.lzke.ai.config;

import org.springframework.amqp.core.Binding;
import org.springframework.amqp.core.BindingBuilder;
import org.springframework.amqp.core.DirectExchange;
import org.springframework.amqp.core.Queue;
import org.springframework.amqp.core.QueueBuilder;
import org.springframework.amqp.support.converter.Jackson2JsonMessageConverter;
import org.springframework.amqp.support.converter.MessageConverter;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class RabbitMQConfig {

    public static final String EXCHANGE = "ai.platform";
    public static final String DLX_EXCHANGE = "ai.platform.dlx";

    public static final String TASK_SYNC_QUEUE = "task.sync";
    public static final String DOCUMENT_PROCESS_QUEUE = "document.process";
    public static final String AUDIT_LOG_QUEUE = "audit.log";
    public static final String CACHE_INVALIDATION_QUEUE = "cache.invalidation";

    public static final String TASK_SYNC_DLQ = "task.sync.dlq";
    public static final String DOCUMENT_PROCESS_DLQ = "document.process.dlq";
    public static final String AUDIT_LOG_DLQ = "audit.log.dlq";

    // ── 交换机 ──────────────────────────────────────────────

    @Bean
    public DirectExchange aiPlatformExchange() {
        return new DirectExchange(EXCHANGE, true, false);
    }

    @Bean
    public DirectExchange dlxExchange() {
        return new DirectExchange(DLX_EXCHANGE, true, false);
    }

    // ── 业务队列（带死信路由）────────────────────────────────

    @Bean
    public Queue taskSyncQueue() {
        return QueueBuilder.durable(TASK_SYNC_QUEUE)
                .deadLetterExchange(DLX_EXCHANGE)
                .deadLetterRoutingKey(TASK_SYNC_DLQ)
                .build();
    }

    @Bean
    public Queue documentProcessQueue() {
        return QueueBuilder.durable(DOCUMENT_PROCESS_QUEUE)
                .deadLetterExchange(DLX_EXCHANGE)
                .deadLetterRoutingKey(DOCUMENT_PROCESS_DLQ)
                .build();
    }

    @Bean
    public Queue auditLogQueue() {
        return QueueBuilder.durable(AUDIT_LOG_QUEUE)
                .deadLetterExchange(DLX_EXCHANGE)
                .deadLetterRoutingKey(AUDIT_LOG_DLQ)
                .build();
    }

    @Bean
    public Queue cacheInvalidationQueue() {
        return new Queue(CACHE_INVALIDATION_QUEUE, true);
    }

    // ── 死信队列 ─────────────────────────────────────────────

    @Bean
    public Queue taskSyncDlq() {
        return QueueBuilder.durable(TASK_SYNC_DLQ).build();
    }

    @Bean
    public Queue documentProcessDlq() {
        return QueueBuilder.durable(DOCUMENT_PROCESS_DLQ).build();
    }

    @Bean
    public Queue auditLogDlq() {
        return QueueBuilder.durable(AUDIT_LOG_DLQ).build();
    }

    // ── 业务队列绑定 ─────────────────────────────────────────

    @Bean
    public Binding taskSyncBinding(Queue taskSyncQueue, DirectExchange aiPlatformExchange) {
        return BindingBuilder.bind(taskSyncQueue).to(aiPlatformExchange).with(TASK_SYNC_QUEUE);
    }

    @Bean
    public Binding documentProcessBinding(Queue documentProcessQueue, DirectExchange aiPlatformExchange) {
        return BindingBuilder.bind(documentProcessQueue).to(aiPlatformExchange).with(DOCUMENT_PROCESS_QUEUE);
    }

    @Bean
    public Binding auditLogBinding(Queue auditLogQueue, DirectExchange aiPlatformExchange) {
        return BindingBuilder.bind(auditLogQueue).to(aiPlatformExchange).with(AUDIT_LOG_QUEUE);
    }

    @Bean
    public Binding cacheInvalidationBinding(Queue cacheInvalidationQueue, DirectExchange aiPlatformExchange) {
        return BindingBuilder.bind(cacheInvalidationQueue).to(aiPlatformExchange).with(CACHE_INVALIDATION_QUEUE);
    }

    // ── 死信队列绑定 ─────────────────────────────────────────

    @Bean
    public Binding taskSyncDlqBinding(Queue taskSyncDlq, DirectExchange dlxExchange) {
        return BindingBuilder.bind(taskSyncDlq).to(dlxExchange).with(TASK_SYNC_DLQ);
    }

    @Bean
    public Binding documentProcessDlqBinding(Queue documentProcessDlq, DirectExchange dlxExchange) {
        return BindingBuilder.bind(documentProcessDlq).to(dlxExchange).with(DOCUMENT_PROCESS_DLQ);
    }

    @Bean
    public Binding auditLogDlqBinding(Queue auditLogDlq, DirectExchange dlxExchange) {
        return BindingBuilder.bind(auditLogDlq).to(dlxExchange).with(AUDIT_LOG_DLQ);
    }

    // ── 消息转换器 ───────────────────────────────────────────

    @Bean
    public MessageConverter jsonMessageConverter() {
        return new Jackson2JsonMessageConverter();
    }
}
