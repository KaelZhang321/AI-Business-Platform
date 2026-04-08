package com.lzke.ai.domain.entity;

import com.baomidou.mybatisplus.annotation.FieldFill;
import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.OffsetDateTime;

/**
 * UI Builder 接口定义实体。
 *
 * <p>对应 `ui_api_endpoints`，保存标准化后的接口路径、方法、Schema 和样例。
 */
@Data
@TableName("ui_api_endpoints")
public class UiApiEndpoint {

    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    private String sourceId;
    private String tagId;
    private String name;
    private String path;
    private String method;
    private String operationSafety;
    private String summary;
    private String requestContentType;
    private String requestSchema;
    private String responseSchema;
    private String sampleRequest;
    private String sampleResponse;
    private String status;

    @TableField(exist = false)
    private String tagName;

    @TableField(fill = FieldFill.INSERT)
    private OffsetDateTime createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private OffsetDateTime updatedAt;
}
