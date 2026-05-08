package com.lzke.ai.application.exam.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

import java.util.List;

/**
 * 单个体检清洗结果汇总。
 */
@Data
@Schema(description = "单个体检清洗结果汇总")
public class PatientExamCleanedSummaryResponse {

    @JsonProperty("total_indicators")
    @Schema(description = "指标总数")
    private Integer totalIndicators;

    @JsonProperty("abnormal_count")
    @Schema(description = "异常指标数")
    private Integer abnormalCount;

    @Schema(description = "指标分类")
    private List<String> categories;
}
