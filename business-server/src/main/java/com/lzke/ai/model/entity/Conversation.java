package com.lzke.ai.model.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;

import java.time.OffsetDateTime;

/**
 * 会话历史表 — 对应文档 4.1.5
 */
@Data
@TableName("conversations")
public class Conversation {

    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    private String userId;
    private String sessionId;
    private String role;
    private String content;
    private String messageType;
    private String metadata;     // JSONB

    @TableField(fill = FieldFill.INSERT)
    private OffsetDateTime createdAt;
}
