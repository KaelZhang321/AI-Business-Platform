package com.lzke.ai.application.workbench.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

/**
 * 医生工作台卡片分组保存请求。
 */
@Data
@Schema(description = "医生工作台卡片分组保存请求")
public class DoctorCardGroupRequest {

    @Schema(description = "分组名称", requiredMode = Schema.RequiredMode.REQUIRED)
    private String groupName;
    @Schema(description = "分组排序")
    private Integer groupSort;
    @Schema(description = "是否展示：1展示，0隐藏")
    private Integer visibleFlag;
    @Schema(description = "状态，例如 active / inactive")
    private String status;
    @Schema(description = "备注")
    private String remark;
}
