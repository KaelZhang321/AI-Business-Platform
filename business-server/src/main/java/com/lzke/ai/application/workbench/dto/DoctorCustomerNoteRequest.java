package com.lzke.ai.application.workbench.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

/**
 * 医生客户便签保存请求。
 */
@Data
@Schema(description = "医生客户便签保存请求")
public class DoctorCustomerNoteRequest {

    @Schema(description = "客户身份证号", requiredMode = Schema.RequiredMode.REQUIRED)
    private String customerIdCard;
    @Schema(description = "便签内容", requiredMode = Schema.RequiredMode.REQUIRED)
    private String noteContent;
    @Schema(description = "排序")
    private Integer sortOrder;
    @Schema(description = "状态，例如 active / inactive")
    private String status;
    @Schema(description = "备注")
    private String remark;
}
