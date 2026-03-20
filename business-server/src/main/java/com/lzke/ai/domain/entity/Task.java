package com.lzke.ai.domain.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;

import java.time.OffsetDateTime;

/**
 * 任务表 — 对应文档 4.1.3
 */
@Data
@TableName("tasks")
public class Task {

    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    private String userId;
    private String sourceSystem;
    private String sourceId;
    private String title;
    private String description;
    private String status;
    private String priority;
    private OffsetDateTime deadline;
    private String externalUrl;

    @TableField(fill = FieldFill.INSERT)
    private OffsetDateTime createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private OffsetDateTime updatedAt;
}
