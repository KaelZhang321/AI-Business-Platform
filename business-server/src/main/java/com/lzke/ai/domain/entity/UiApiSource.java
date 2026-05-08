package com.lzke.ai.domain.entity;

import com.baomidou.mybatisplus.annotation.FieldFill;
import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.OffsetDateTime;

/**
 * UI Builder 接口源实体。
 *
 * <p>对应 `ui_api_sources`，用于描述一个可被导入或联调的外部接口系统。
 */
@Data
@TableName("ui_api_sources")
public class UiApiSource {

    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    private String name;
    private String code;
    private String description;
    private String sourceType;
    private String baseUrl;
    private String docUrl;
    private String authType;
    private String authConfig;
    private String defaultHeaders;
    private String env;
    private String status;
    private String createdBy;

    @TableField(fill = FieldFill.INSERT)
    private OffsetDateTime createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private OffsetDateTime updatedAt;
}
