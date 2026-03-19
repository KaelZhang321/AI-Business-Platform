package com.lzke.ai.model.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;

import java.time.OffsetDateTime;

/**
 * 审计日志表 — 对应文档 4.1.6
 */
@Data
@TableName("audit_logs")
public class AuditLog {

    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    private String traceId;
    private String userId;
    private String intent;
    private String model;
    private Integer inputTokens;
    private Integer outputTokens;
    private Integer latencyMs;
    private String status;

    @TableField(fill = FieldFill.INSERT)
    private OffsetDateTime createdAt;
}
