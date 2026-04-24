package com.lzke.ai.application.exam.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;
import lombok.Data;

/**
 * 患者 HIS 单项结果查询请求。
 */
@Data
@Schema(description = "患者 HIS 单项结果查询请求")
public class PatientHisItemResultQueryRequest {

    @NotBlank(message = "身份证号不能为空")
    @Schema(description = "身份证号", requiredMode = Schema.RequiredMode.REQUIRED, example = "110101199001011234")
    private String idCard;
}
