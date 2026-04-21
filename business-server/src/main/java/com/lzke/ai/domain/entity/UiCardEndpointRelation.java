package com.lzke.ai.domain.entity;

import com.baomidou.mybatisplus.annotation.FieldFill;
import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.OffsetDateTime;

/**
 * UI Builder 卡片和接口关联关系。
 */
@Data
@TableName("ui_card_endpoint_relations")
public class UiCardEndpointRelation {

    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    private String cardId;
    private String endpointId;
    private Integer sortOrder;

    @TableField(exist = false)
    private String endpointName;

    @TableField(exist = false)
    private String endpointPath;

    @TableField(exist = false)
    private String endpointMethod;

    @TableField(exist = false)
    private String endpointStatus;

    @TableField(exist = false)
    private String sourceId;

    @TableField(exist = false)
    private String sourceName;

    @TableField(exist = false)
    private String tagName;
    
    @TableField(exist = false)
    private String operationSafety;

    @TableField(fill = FieldFill.INSERT)
    private OffsetDateTime createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private OffsetDateTime updatedAt;
}
