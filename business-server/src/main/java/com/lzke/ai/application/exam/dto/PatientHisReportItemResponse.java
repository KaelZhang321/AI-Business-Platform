package com.lzke.ai.application.exam.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

/**
 * 患者 HIS 检验报告明细项。
 */
@Data
@Schema(description = "患者 HIS 检验报告明细项")
public class PatientHisReportItemResponse {

    @Schema(description = "报告项目编码")
    private String reportItemCode;
    @Schema(description = "报告项目名称")
    private String reportItemName;
    @Schema(description = "结果值")
    private String resultValue;
    @Schema(description = "打印上下文")
    private String printContext;
    @Schema(description = "单位")
    private String unit;
    @Schema(description = "异常标识")
    private String abnormalIndicator;
    @Schema(description = "申请时间，yyyy-MM-dd HH:mm:ss")
    private String requestedTime;
    @Schema(description = "报告时间，yyyy-MM-dd HH:mm:ss")
    private String reportTime;
    @Schema(description = "来源表唯一ID")
    private String uniqueId;
}
