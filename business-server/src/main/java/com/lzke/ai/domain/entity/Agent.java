package com.lzke.ai.domain.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;

import java.math.BigDecimal;
import java.time.OffsetDateTime;

/**
 * 智能体配置表 — 对应文档 4.1.11
 */
@Data
@TableName("agents")
public class Agent {

    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    private String name;
    private String description;
    private String type;
    private String model;
    private String systemPrompt;
    private String tools;             // JSONB
    private BigDecimal temperature;
    private Integer maxTokens;
    private String status;
    private String createdBy;

    @TableField(fill = FieldFill.INSERT)
    private OffsetDateTime createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private OffsetDateTime updatedAt;
}
