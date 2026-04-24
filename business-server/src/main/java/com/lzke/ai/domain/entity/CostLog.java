package com.lzke.ai.domain.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;

import java.math.BigDecimal;
import java.time.OffsetDateTime;

/**
 * 成本日志表 — 对应文档 4.1.12
 */
@Data
@TableName("cost_logs")
public class CostLog {

    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    private String traceId;
    private String userId;
    private String model;
    private String provider;
    private Integer inputTokens;
    private Integer outputTokens;
    private BigDecimal costUsd;

    @TableField(fill = FieldFill.INSERT)
    private OffsetDateTime createdAt;
}
