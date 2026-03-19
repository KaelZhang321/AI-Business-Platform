package com.lzke.ai.service;

import org.springframework.stereotype.Service;

import java.util.Collections;
import java.util.Map;

@Service
public class AuditService {

    public Map<String, Object> queryLogs(String userId, String action, int page, int size) {
        // TODO: 查询审计日志
        return Map.of("data", Collections.emptyList(), "total", 0, "page", page, "size", size);
    }
}
