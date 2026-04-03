package com.lzke.ai.domain.entity;

import com.baomidou.mybatisplus.annotation.FieldFill;
import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.OffsetDateTime;

/**
 * UI Builder 页面实体。
 *
 * <p>对应 `ui_pages`，描述项目下某个可生成 json-render spec 的页面。
 */
@Data
@TableName("ui_pages")
public class UiPage {

    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    private String projectId;
    private String name;
    private String code;
    private String title;
    private String routePath;
    private String rootNodeId;
    private String layoutType;
    private String status;

    @TableField(fill = FieldFill.INSERT)
    private OffsetDateTime createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private OffsetDateTime updatedAt;
}
