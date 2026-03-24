package com.lzke.ai.domain.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;

import java.time.OffsetDateTime;
import java.util.UUID;

/**
 * 用户表 — 对应文档 4.1.1
 */
@Data
@TableName("users")
public class User {

    @TableId
    private UUID id;

    private String username;
    private String displayName;
    private String email;
    private String department;
    private String role;
    private String status;
    @TableField("password_hash")
    private String passwordHash;

    @TableField(fill = FieldFill.INSERT)
    private OffsetDateTime createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private OffsetDateTime updatedAt;
}
