package com.lzke.ai.domain.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;

import java.time.OffsetDateTime;

/**
 * API密钥表 — 对应文档 4.1.7
 */
@Data
@TableName("api_keys")
public class ApiKey {

    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    private String name;
    private String keyHash;
    private String userId;
    private String permissions;       // JSONB
    private Integer rateLimit;
    private OffsetDateTime expiresAt;
    private String status;
    private OffsetDateTime lastUsedAt;

    @TableField(fill = FieldFill.INSERT)
    private OffsetDateTime createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private OffsetDateTime updatedAt;
}
