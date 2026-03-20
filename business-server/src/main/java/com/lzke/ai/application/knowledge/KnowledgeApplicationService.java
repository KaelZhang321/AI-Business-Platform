package com.lzke.ai.application.knowledge;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.lzke.ai.application.dto.DocumentCreateRequest;
import com.lzke.ai.domain.entity.Document;
import com.lzke.ai.infrastructure.persistence.mapper.DocumentMapper;
import com.lzke.ai.interfaces.dto.DocumentVO;
import com.lzke.ai.interfaces.dto.PageResult;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
@RequiredArgsConstructor
public class KnowledgeApplicationService {

    private final DocumentMapper documentMapper;

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

        DocumentVO vo = new DocumentVO();
        vo.setId(doc.getId());
        vo.setTitle(doc.getTitle());
        vo.setCategory(doc.getCategory());
        vo.setStatus(doc.getStatus());
        return vo;
    }

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
