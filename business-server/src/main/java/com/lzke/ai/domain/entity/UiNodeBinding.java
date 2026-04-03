package com.lzke.ai.domain.entity;

import com.baomidou.mybatisplus.annotation.FieldFill;
import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.OffsetDateTime;

/**
 * UI Builder 节点字段绑定实体。
 *
 * <p>对应 `ui_node_bindings`，保存节点 props 与接口响应字段之间的映射规则。
 */
@Data
@TableName("ui_node_bindings")
public class UiNodeBinding {

    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    private String nodeId;
    private String endpointId;
    private String bindingType;
    private String targetProp;
    private String sourcePath;
    private String transformScript;
    private String defaultValue;
    private Boolean requiredFlag;

    @TableField(fill = FieldFill.INSERT)
    private OffsetDateTime createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private OffsetDateTime updatedAt;
}
