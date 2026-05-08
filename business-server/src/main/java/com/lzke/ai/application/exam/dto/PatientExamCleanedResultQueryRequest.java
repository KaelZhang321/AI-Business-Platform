package com.lzke.ai.application.exam.dto;

import com.fasterxml.jackson.annotation.JsonAlias;
import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;
import lombok.Data;

/**
 * 单个体检清洗结果查询请求。
 */
@Data
@Schema(description = "单个体检清洗结果查询请求")
public class PatientExamCleanedResultQueryRequest {

    @NotBlank(message = "studyId不能为空")
    @JsonAlias("study_id")
    @Schema(description = "体检主单号", requiredMode = Schema.RequiredMode.REQUIRED, example = "2512125012")
    private String studyId;
}
