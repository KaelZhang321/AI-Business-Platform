package com.lzke.ai.application.workbench.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

/**
 * 医生客户定制卡片保存请求。
 */
@Data
@Schema(description = "医生客户定制卡片保存请求")
public class DoctorCustomerCardCustomizeRequest {

    @Schema(description = "登录员工ID", requiredMode = Schema.RequiredMode.REQUIRED)
    private String employeeId;
    @Schema(description = "登录员工名称")
    private String employeeName;
    @Schema(description = "客户身份证号", requiredMode = Schema.RequiredMode.REQUIRED)
    private String customerIdCard;
    @Schema(description = "收藏名称", requiredMode = Schema.RequiredMode.REQUIRED)
    private String favoriteName;
    @Schema(description = "卡片key")
    private String cardKey;
    @Schema(description = "分组key")
    private String groupKey;
    @Schema(description = "卡片JSON内容", requiredMode = Schema.RequiredMode.REQUIRED)
    private String cardJson;
    @Schema(description = "排序")
    private Integer sortOrder;
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
