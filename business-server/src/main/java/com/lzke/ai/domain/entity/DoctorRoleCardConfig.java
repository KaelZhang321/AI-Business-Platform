package com.lzke.ai.domain.entity;

import com.baomidou.mybatisplus.annotation.FieldFill;
import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;

/**
 * 医生角色卡片配置。
 */
@Data
@TableName("doctor_role_card_config")
@Schema(description = "医生角色卡片配置")
public class DoctorRoleCardConfig {

    @TableId(type = IdType.ASSIGN_UUID)
    @Schema(description = "主键ID")
    private String id;
    @Schema(description = "角色ID")
    private String roleId;
    @Schema(description = "角色编码")
    private String roleCode;
    @Schema(description = "角色名称")
    private String roleName;
    @Schema(description = "卡片配置JSON")
    private String cardSchemaJson;
    @TableField(exist = false)
    @Schema(description = "卡片关联接口关系，key为cardId")
    private Map<String, List<UiCardEndpointRelation>> cardEndpointRelations;
    @Schema(description = "是否展示：1展示，0隐藏")
    private Integer visibleFlag;
    @Schema(description = "状态，例如 active / inactive")
    private String status;
    @Schema(description = "备注")
    private String remark;
    @Schema(description = "创建人ID")
    private String createdBy;
    @Schema(description = "创建人名称")
    private String createdByName;
    @Schema(description = "更新人ID")
    private String updatedBy;
    @Schema(description = "更新人名称")
    private String updatedByName;

    @TableField(fill = FieldFill.INSERT)
    @Schema(description = "创建时间")
    private OffsetDateTime createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    @Schema(description = "更新时间")
    private OffsetDateTime updatedAt;
}
