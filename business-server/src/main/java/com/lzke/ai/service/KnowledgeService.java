package com.lzke.ai.service;

import org.springframework.stereotype.Service;

import java.util.Collections;
import java.util.Map;

@Service
public class KnowledgeService {

    public Map<String, Object> createDocument(Map<String, Object> request) {
        // TODO: 存储文档元数据到PostgreSQL，文件上传MinIO，触发向量化
        return Map.of("status", "created", "message", "知识库文档管理服务开发中");
    }

    public Map<String, Object> listDocuments(int page, int size) {
        // TODO: 查询文档列表
        return Map.of("data", Collections.emptyList(), "total", 0, "page", page, "size", size);
    }
}
