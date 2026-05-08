package com.lzke.ai.application.exam.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

import java.util.List;

/**
 * 单个体检清洗结果响应。
 */
@Data
@Schema(description = "单个体检清洗结果响应")
public class PatientExamCleanedResultResponse {

    @JsonProperty("study_id")
    @Schema(description = "体检主单号")
    private String studyId;

    @JsonProperty("patient_name")
    @Schema(description = "患者姓名")
    private String patientName;

    @Schema(description = "性别")
    private String gender;

    @JsonProperty("exam_time")
    @Schema(description = "体检时间")
    private String examTime;

    @JsonProperty("package_name")
    @Schema(description = "套餐名称")
    private String packageName;

    @Schema(description = "汇总信息")
    private PatientExamCleanedSummaryResponse summary;

    @Schema(description = "清洗后的指标列表")
    private List<PatientExamCleanedIndicatorResponse> indicators;
}
