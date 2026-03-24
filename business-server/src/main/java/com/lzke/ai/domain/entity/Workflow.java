package com.lzke.ai.domain.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;

import java.time.OffsetDateTime;

/**
 * 工作流定义表 — 对应文档 4.1.9
 */
@Data
@TableName("workflows")
public class Workflow {

    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    private String name;
    private String description;
    private String category;
    private String bpmnXml;
    private Integer version;
    private String status;
    private String createdBy;

    @TableField(fill = FieldFill.INSERT)
    private OffsetDateTime createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private OffsetDateTime updatedAt;
}
