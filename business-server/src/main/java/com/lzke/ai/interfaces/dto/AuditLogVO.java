package com.lzke.ai.interfaces.dto;

import lombok.Data;

/**
 * 审计日志视图对象
 */
@Data
public class AuditLogVO {

    private String id;
    private String traceId;
    private String userId;
    private String intent;
    private String model;
    private Integer inputTokens;
    private Integer outputTokens;
    private Integer latencyMs;
    private String status;
    private String createdAt;
}
