package com.lzke.ai.config;

import org.springframework.amqp.core.Binding;
import org.springframework.amqp.core.BindingBuilder;
import org.springframework.amqp.core.DirectExchange;
import org.springframework.amqp.core.Queue;
import org.springframework.amqp.support.converter.Jackson2JsonMessageConverter;
import org.springframework.amqp.support.converter.MessageConverter;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class RabbitMQConfig {

    public static final String EXCHANGE = "ai.platform";
    public static final String TASK_SYNC_QUEUE = "task.sync";
    public static final String DOCUMENT_PROCESS_QUEUE = "document.process";
    public static final String AUDIT_LOG_QUEUE = "audit.log";

    @Bean
    public DirectExchange aiPlatformExchange() {
        return new DirectExchange(EXCHANGE, true, false);
    }

    @Bean
    public Queue taskSyncQueue() {
        return new Queue(TASK_SYNC_QUEUE, true);
    }

    @Bean
    public Queue documentProcessQueue() {
        return new Queue(DOCUMENT_PROCESS_QUEUE, true);
    }

    @Bean
    public Queue auditLogQueue() {
        return new Queue(AUDIT_LOG_QUEUE, true);
    }

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
    public MessageConverter jsonMessageConverter() {
        return new Jackson2JsonMessageConverter();
    }
}
