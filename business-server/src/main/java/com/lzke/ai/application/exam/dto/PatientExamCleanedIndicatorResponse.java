package com.lzke.ai.application.exam.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

/**
 * 单个体检清洗后的指标。
 */
@Data
@Schema(description = "单个体检清洗后的指标")
public class PatientExamCleanedIndicatorResponse {

    @JsonProperty("standard_code")
    @Schema(description = "标准指标编码")
    private String standardCode;

    @JsonProperty("standard_name")
    @Schema(description = "标准指标名称")
    private String standardName;

    @Schema(description = "指标分类")
    private String category;

    @Schema(description = "结果值")
    private String value;

    @Schema(description = "单位")
    private String unit;

    @JsonProperty("reference_range")
    @Schema(description = "参考范围")
    private String referenceRange;

    @JsonProperty("ref_min")
    @Schema(description = "参考下限")
    private String refMin;

    @JsonProperty("ref_max")
    @Schema(description = "参考上限")
    private String refMax;

    @JsonProperty("is_abnormal")
    @Schema(description = "是否异常")
    private Boolean abnormal;

    @JsonProperty("abnormal_direction")
    @Schema(description = "异常方向：high/low")
    private String abnormalDirection;
}
