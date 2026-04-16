package com.lzke.ai.application.workbench.dto;

import com.lzke.ai.application.dto.PageQuery;
import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;
import lombok.EqualsAndHashCode;

/**
 * 医生角色卡片配置分页查询条件。
 */
@Data
@EqualsAndHashCode(callSuper = true)
@Schema(description = "医生角色卡片配置分页查询条件")
public class DoctorRoleCardConfigQueryRequest extends PageQuery {

    @Schema(description = "角色ID")
    private String roleId;
    @Schema(description = "角色编码")
    private String roleCode;
    @Schema(description = "卡片分组key")
    private String groupKey;
    @Schema(description = "卡片名称，支持模糊查询")
    private String cardName;
    @Schema(description = "状态，例如 active / inactive")
    private String status;
    @Schema(description = "是否展示：1展示，0隐藏")
    private Integer visibleFlag;
}
