package com.lzke.ai.domain.entity;

import com.baomidou.mybatisplus.annotation.FieldFill;
import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.OffsetDateTime;

/**
 * UI Builder 接口与角色关系实体。
 *
 * <p>该表用于记录“某个接口定义可以被哪个 IAM 角色使用”，既支持在前端工作台
 * 按角色筛选已关联接口，也支持将现有接口定义显式绑定到某个角色。
 *
 * <p>表内除了角色 ID 以外，还会冗余保存 `roleCode`、`roleName`，
 * 这样前端列表查询时无需每次再去远程角色中心做 Join。
 */
@Data
@TableName("ui_api_endpoint_roles")
public class UiApiEndpointRole {

    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    private String endpointId;
    private String roleId;
    private String roleCode;
    private String roleName;
    private String createdBy;

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

    @TableField(fill = FieldFill.INSERT)
    private OffsetDateTime createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private OffsetDateTime updatedAt;
}
