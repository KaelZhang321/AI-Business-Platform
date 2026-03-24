package com.lzke.ai.listener;

import com.lzke.ai.config.RabbitMQConfig;
import com.lzke.ai.domain.entity.Document;
import com.lzke.ai.infrastructure.persistence.mapper.DocumentMapper;
import com.rabbitmq.client.Channel;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.amqp.rabbit.annotation.RabbitListener;
import org.springframework.amqp.support.AmqpHeaders;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.*;
import org.springframework.messaging.handler.annotation.Header;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestTemplate;

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

    private final DocumentMapper documentMapper;
    private final RestTemplate restTemplate;

    @Value("${ai-gateway.base-url:http://localhost:8000}")
    private String aiGatewayBaseUrl;

    @RabbitListener(queues = RabbitMQConfig.DOCUMENT_PROCESS_QUEUE)
    public void onDocumentProcess(Map<String, Object> message, Channel channel,
                                  @Header(AmqpHeaders.DELIVERY_TAG) long deliveryTag) throws IOException {
        String documentId = String.valueOf(message.get("documentId"));
        String title = String.valueOf(message.get("title"));
        log.info("收到文档处理消息: documentId={}, title={}", documentId, title);

        try {
            // 1. 读取文档内容
            Document doc = documentMapper.selectById(documentId);
            if (doc == null) {
                log.warn("文档不存在, 跳过处理: documentId={}", documentId);
                channel.basicAck(deliveryTag, false);
                return;
            }

            // 2. 调用 AI 网关 /api/v1/knowledge/ingest 接口
            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.APPLICATION_JSON);
            Map<String, Object> payload = Map.of(
                    "doc_id", documentId,
                    "title", doc.getTitle(),
                    "content", doc.getContent() != null ? doc.getContent() : "",
                    "category", doc.getCategory() != null ? doc.getCategory() : "",
                    "source", doc.getSource() != null ? doc.getSource() : ""
            );
            HttpEntity<Map<String, Object>> request = new HttpEntity<>(payload, headers);

            ResponseEntity<Map> resp = restTemplate.exchange(
                    aiGatewayBaseUrl + "/api/v1/knowledge/ingest",
                    HttpMethod.POST, request, Map.class);

            int chunkCount = 0;
            if (resp.getStatusCode().is2xxSuccessful() && resp.getBody() != null) {
                Object chunks = resp.getBody().get("chunk_count");
                if (chunks instanceof Number) {
                    chunkCount = ((Number) chunks).intValue();
                }
            }

            // 3. 更新文档状态为 processed，更新 chunk_count
            doc.setStatus("processed");
            doc.setChunkCount(chunkCount);
            documentMapper.updateById(doc);

            log.info("文档处理完成: documentId={}, chunkCount={}", documentId, chunkCount);
            channel.basicAck(deliveryTag, false);
        } catch (Exception e) {
            log.error("文档处理失败: documentId={}, error={}", documentId, e.getMessage(), e);
            // 更新状态为 failed 以便排查
            try {
                Document doc = documentMapper.selectById(documentId);
                if (doc != null) {
                    doc.setStatus("failed");
                    documentMapper.updateById(doc);
                }
            } catch (Exception updateEx) {
                log.warn("更新文档失败状态异常: {}", updateEx.getMessage());
            }
            channel.basicNack(deliveryTag, false, false);
        }
    }
}
