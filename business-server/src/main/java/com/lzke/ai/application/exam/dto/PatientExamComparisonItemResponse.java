package com.lzke.ai.application.exam.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

import java.util.Map;

/**
 * 患者多次体检指标对比项。
 */
@Data
@Schema(description = "患者多次体检指标对比项")
public class PatientExamComparisonItemResponse {

    @JsonProperty("standard_code")
    @Schema(description = "标准指标编码")
    private String standardCode;

    @JsonProperty("standard_name")
    @Schema(description = "标准指标名称")
    private String standardName;

    @Schema(description = "指标分类")
    private String category;

    @Schema(description = "单位")
    private String unit;

    @Schema(description = "按体检日期聚合的指标值")
    private Map<String, Object> values;

    @Schema(description = "趋势：numeric模式为 ↑/↓/=，text模式为 变化/一致")
    private String trend;

    @JsonProperty("ref_min")
    @Schema(description = "参考下限")
    private Double refMin;

    @JsonProperty("ref_max")
    @Schema(description = "参考上限")
    private Double refMax;
}
