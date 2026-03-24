package com.lzke.ai.listener;

import com.lzke.ai.config.RabbitMQConfig;
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
 * 文档处理消费者 — 监听 document.process 队列。
 * 收到消息后触发文档分块、向量化等异步流程。
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class DocumentProcessListener {

    @RabbitListener(queues = RabbitMQConfig.DOCUMENT_PROCESS_QUEUE)
    public void onDocumentProcess(Map<String, Object> message, Channel channel,
                                  @Header(AmqpHeaders.DELIVERY_TAG) long deliveryTag) throws IOException {
        String documentId = String.valueOf(message.get("documentId"));
        String title = String.valueOf(message.get("title"));
        log.info("收到文档处理消息: documentId={}, title={}", documentId, title);

        try {
            // TODO: 调用 AI 网关进行文档分块和向量化
            // 1. 读取文档内容
            // 2. 调用 AI 网关 /api/v1/knowledge/ingest 接口
            // 3. 更新文档状态为 processed，更新 chunk_count
            log.info("文档处理完成: documentId={}", documentId);
            channel.basicAck(deliveryTag, false);
        } catch (Exception e) {
            log.error("文档处理失败: documentId={}, error={}", documentId, e.getMessage(), e);
            channel.basicNack(deliveryTag, false, true);
        }
    }
}
