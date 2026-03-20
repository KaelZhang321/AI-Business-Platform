package com.lzke.ai.domain.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;

import java.time.OffsetDateTime;

/**
 * 知识库文档表 — 对应文档 4.1.4
 */
@Data
@TableName("documents")
public class Document {

    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    private String title;
    private String content;
    private String category;
    private String tags;            // JSONB
    private String source;
    private Integer chunkCount;
    private String status;

    @TableField(fill = FieldFill.INSERT)
    private OffsetDateTime createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private OffsetDateTime updatedAt;
}
