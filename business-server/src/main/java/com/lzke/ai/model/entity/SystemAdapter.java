package com.lzke.ai.model.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;

import java.time.OffsetDateTime;

/**
 * 系统适配器表 — 对应文档 4.1.2
 */
@Data
@TableName("system_adapters")
public class SystemAdapter {

    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    private String name;
    private String code;
    private String type;
    private String endpoint;
    private String authType;
    private String config;       // JSONB
    private String status;

    @TableField(fill = FieldFill.INSERT)
    private OffsetDateTime createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private OffsetDateTime updatedAt;
}
