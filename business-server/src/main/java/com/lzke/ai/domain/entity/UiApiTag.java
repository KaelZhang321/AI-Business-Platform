package com.lzke.ai.domain.entity;

import com.baomidou.mybatisplus.annotation.FieldFill;
import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.OffsetDateTime;

/**
 * UI Builder 接口标签实体。
 *
 * <p>对应 `ui_api_tags`，用于在接口源和接口定义之间增加一层标签分类。
 */
@Data
@TableName("ui_api_tags")
public class UiApiTag {

    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    private String sourceId;
    private String name;
    private String code;
    private String description;

    @TableField(fill = FieldFill.INSERT)
    private OffsetDateTime createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private OffsetDateTime updatedAt;
}
