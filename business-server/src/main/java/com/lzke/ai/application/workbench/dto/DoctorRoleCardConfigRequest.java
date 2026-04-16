package com.lzke.ai.application.workbench.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

/**
 * 医生角色卡片配置保存请求。
 */
@Data
@Schema(description = "医生角色卡片配置保存请求")
public class DoctorRoleCardConfigRequest {

    @Schema(description = "角色ID", requiredMode = Schema.RequiredMode.REQUIRED)
    private String roleId;
    @Schema(description = "角色编码")
    private String roleCode;
    @Schema(description = "角色名称")
    private String roleName;
    @Schema(description = "卡片分组key", requiredMode = Schema.RequiredMode.REQUIRED)
    private String groupKey;
    @Schema(description = "卡片分组名称", requiredMode = Schema.RequiredMode.REQUIRED)
    private String groupName;
    @Schema(description = "分组排序")
    private Integer groupSort;
    @Schema(description = "卡片key", requiredMode = Schema.RequiredMode.REQUIRED)
    private String cardKey;
    @Schema(description = "卡片名称", requiredMode = Schema.RequiredMode.REQUIRED)
    private String cardName;
    @Schema(description = "卡片类型，例如 json_render")
    private String cardType;
    @Schema(description = "卡片配置JSON")
    private String cardSchemaJson;
    @Schema(description = "卡片排序")
    private Integer cardSort;
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
}
