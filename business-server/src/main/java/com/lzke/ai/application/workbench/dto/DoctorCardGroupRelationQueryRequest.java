package com.lzke.ai.application.workbench.dto;

import com.lzke.ai.application.dto.PageQuery;
import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;
import lombok.EqualsAndHashCode;

/**
 * 医生工作台分组卡片关系分页查询条件。
 */
@Data
@EqualsAndHashCode(callSuper = true)
@Schema(description = "医生工作台分组卡片关系分页查询条件")
public class DoctorCardGroupRelationQueryRequest extends PageQuery {

    @Schema(description = "分组ID")
    private String groupId;
    @Schema(description = "卡片配置ID")
    private String cardConfigId;
    @Schema(description = "状态，例如 active / inactive")
    private String status;
    @Schema(description = "是否展示：1展示，0隐藏")
    private Integer visibleFlag;
}
