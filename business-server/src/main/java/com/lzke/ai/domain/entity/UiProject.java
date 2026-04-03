package com.lzke.ai.domain.entity;

import com.baomidou.mybatisplus.annotation.FieldFill;
import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.OffsetDateTime;

/**
 * UI Builder 项目实体。
 *
 * <p>对应 `ui_projects`，是页面配置和版本发布的顶层业务容器。
 */
@Data
@TableName("ui_projects")
public class UiProject {

    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    private String name;
    private String code;
    private String description;
    private String category;
    private String status;
    private String createdBy;

    @TableField(fill = FieldFill.INSERT)
    private OffsetDateTime createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private OffsetDateTime updatedAt;
}
