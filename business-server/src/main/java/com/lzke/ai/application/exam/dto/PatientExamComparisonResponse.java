package com.lzke.ai.application.exam.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

import java.util.List;

/**
 * 患者多次体检指标对比响应。
 */
@Data
@Schema(description = "患者多次体检指标对比响应")
public class PatientExamComparisonResponse {

    @JsonProperty("patient_id")
    @Schema(description = "脱敏身份证号")
    private String patientId;

    @Schema(description = "对比模式：numeric/text")
    private String mode;

    @JsonProperty("exam_dates")
    @Schema(description = "参与对比的体检日期")
    private List<String> examDates;

    @Schema(description = "指标对比列表")
    private List<PatientExamComparisonItemResponse> comparisons;
}
