package com.lzke.ai.application.exam.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;
import lombok.Data;

/**
 * 患者多次体检指标对比查询请求。
 */
@Data
@Schema(description = "患者多次体检指标对比查询请求")
public class PatientExamComparisonQueryRequest {

    @NotBlank(message = "身份证号不能为空")
    @Schema(description = "身份证号或Base64密文身份证", requiredMode = Schema.RequiredMode.REQUIRED)
    private String sfzh;

    @Schema(description = "指标分类过滤")
    private String category;

    @Schema(description = "对比模式：numeric/text，默认numeric")
    private String mode = "numeric";
}
