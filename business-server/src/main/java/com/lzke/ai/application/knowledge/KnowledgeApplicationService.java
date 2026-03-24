package com.lzke.ai.application.knowledge;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.lzke.ai.application.dto.DocumentCreateRequest;
import com.lzke.ai.domain.entity.Document;
import com.lzke.ai.infrastructure.persistence.mapper.DocumentMapper;
import com.lzke.ai.interfaces.dto.DocumentVO;
import com.lzke.ai.interfaces.dto.PageResult;
import com.lzke.ai.config.RabbitMQConfig;
import lombok.RequiredArgsConstructor;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.cache.annotation.CacheEvict;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;

@Service
@RequiredArgsConstructor
public class KnowledgeApplicationService {

    private final DocumentMapper documentMapper;
    private final RabbitTemplate rabbitTemplate;

    @CacheEvict(cacheNames = "knowledge:documents", allEntries = true)
    public DocumentVO createDocument(DocumentCreateRequest request) {
        Document doc = new Document();
        doc.setTitle(request.getTitle());
        doc.setContent(request.getContent());
        doc.setCategory(request.getCategory());
        doc.setTags(request.getTags() != null ? request.getTags().toString() : "[]");
        doc.setSource(request.getSource());
        doc.setStatus("pending");
        doc.setChunkCount(0);
        documentMapper.insert(doc);

        // 发送文档处理消息到 MQ（异步触发分块/向量化）
        rabbitTemplate.convertAndSend(
                RabbitMQConfig.EXCHANGE,
                RabbitMQConfig.DOCUMENT_PROCESS_QUEUE,
                Map.of("documentId", doc.getId().toString(), "title", doc.getTitle())
        );

        DocumentVO vo = new DocumentVO();
        vo.setId(doc.getId());
        vo.setTitle(doc.getTitle());
        vo.setCategory(doc.getCategory());
        vo.setStatus(doc.getStatus());
        return vo;
    }

    @Cacheable(cacheNames = "knowledge:documents", key = "#page + ':' + #size")
    public PageResult<DocumentVO> listDocuments(int page, int size) {
        Page<Document> pageParam = new Page<>(page, size);
        LambdaQueryWrapper<Document> wrapper = new LambdaQueryWrapper<>();
        wrapper.orderByDesc(Document::getCreatedAt);
        Page<Document> result = documentMapper.selectPage(pageParam, wrapper);

        List<DocumentVO> voList = result.getRecords().stream().map(doc -> {
            DocumentVO vo = new DocumentVO();
            vo.setId(doc.getId());
            vo.setTitle(doc.getTitle());
            vo.setCategory(doc.getCategory());
            vo.setChunkCount(doc.getChunkCount());
            vo.setStatus(doc.getStatus());
            vo.setCreatedAt(doc.getCreatedAt() != null ? doc.getCreatedAt().toString() : null);
            return vo;
        }).toList();

        return PageResult.of(voList, result.getTotal(), page, size);
    }
}
