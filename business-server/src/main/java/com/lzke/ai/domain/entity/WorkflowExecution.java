package com.lzke.ai.domain.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;

import java.time.OffsetDateTime;

/**
 * 工作流执行表 — 对应文档 4.1.10
 */
@Data
@TableName("workflow_executions")
public class WorkflowExecution {

    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    private String workflowId;
    private String initiatorId;
    private String currentNode;
    private String variables;         // JSONB
    private String status;
    private OffsetDateTime startedAt;
    private OffsetDateTime completedAt;

    @TableField(fill = FieldFill.INSERT)
    private OffsetDateTime createdAt;
}
