package com.lzke.ai.config;

import org.springframework.amqp.core.Queue;
import org.springframework.amqp.support.converter.Jackson2JsonMessageConverter;
import org.springframework.amqp.support.converter.MessageConverter;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class RabbitMQConfig {

    public static final String TASK_SYNC_QUEUE = "task.sync";
    public static final String DOCUMENT_PROCESS_QUEUE = "document.process";
    public static final String AUDIT_LOG_QUEUE = "audit.log";

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
    public MessageConverter jsonMessageConverter() {
        return new Jackson2JsonMessageConverter();
    }
}
