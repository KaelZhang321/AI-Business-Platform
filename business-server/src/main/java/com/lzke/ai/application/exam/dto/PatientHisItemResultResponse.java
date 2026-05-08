package com.lzke.ai.application.exam.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

import java.util.List;

/**
 * 患者 HIS 单项检查结果。
 */
@Data
@Schema(description = "患者 HIS 单项检查结果")
public class PatientHisItemResultResponse {

    @Schema(description = "病历号")
    private String patientNo;
    @Schema(description = "患者姓名")
    private String patientName;
    @Schema(description = "性别")
    private String genderName;
    @Schema(description = "生日，yyyy-MM-dd")
    private String birthdayDate;
    @Schema(description = "年龄")
    private Integer age;
    @Schema(description = "身份证号")
    private String idCard;
    @Schema(description = "结果类型：LIS/PACS")
    private String resultType;
    @Schema(description = "来源类型")
    private String sourceType;
    @Schema(description = "检验/检查单号")
    private String testNo;
    @Schema(description = "项目编码")
    private String itemCode;
    @Schema(description = "项目名称")
    private String itemName;
    @Schema(description = "报告项目编码")
    private String reportItemCode;
    @Schema(description = "报告项目名称")
    private String reportItemName;
    @Schema(description = "结果值或影像诊断")
    private String resultValue;
    @Schema(description = "打印上下文或影像所见")
    private String printContext;
    @Schema(description = "单位")
    private String unit;
    @Schema(description = "异常标识")
    private String abnormalIndicator;
    @Schema(description = "申请/检查时间，yyyy-MM-dd HH:mm:ss")
    private String requestedTime;
    @Schema(description = "报告时间，yyyy-MM-dd HH:mm:ss")
    private String reportTime;
    @Schema(description = "设备类型")
    private String deviceType;
    @Schema(description = "设备名称")
    private String deviceName;
    @Schema(description = "检查状态")
    private String studyStatusName;
    @Schema(description = "影像建议")
    private String reportAdvice;
    @Schema(description = "机构编码")
    private String companyCode;
    @Schema(description = "机构名称")
    private String companyName;
    @Schema(description = "来源表唯一ID")
    private String uniqueId;
    @Schema(description = "LIS检验报告明细项；PACS结果为空")
    private List<PatientHisReportItemResponse> items;
}
