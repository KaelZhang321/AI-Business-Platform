package com.lzke.ai.application.workbench.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

/**
 * 医生工作台分组卡片关系保存请求。
 */
@Data
@Schema(description = "医生工作台分组卡片关系保存请求")
public class DoctorCardGroupRelationRequest {

    @Schema(description = "分组ID", requiredMode = Schema.RequiredMode.REQUIRED)
    private String groupId;
    @Schema(description = "卡片配置ID", requiredMode = Schema.RequiredMode.REQUIRED)
    private String cardConfigId;
    @Schema(description = "卡片排序")
    private Integer cardSort;
    @Schema(description = "是否展示：1展示，0隐藏")
    private Integer visibleFlag;
    @Schema(description = "状态，例如 active / inactive")
    private String status;
    @Schema(description = "备注")
    private String remark;
}
