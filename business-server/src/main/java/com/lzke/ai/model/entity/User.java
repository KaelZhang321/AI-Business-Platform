package com.lzke.ai.model.entity;

import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.OffsetDateTime;
import java.util.UUID;

@Data
@TableName("users")
public class User {
    private UUID id;
    private String username;
    private String displayName;
    private String email;
    private String department;
    private String role;
    private String status;
    @TableField("password_hash")
    private String passwordHash;
    private OffsetDateTime createdAt;
    private OffsetDateTime updatedAt;
}
