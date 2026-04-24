package com.lzke.ai.application.exam.dto;

import lombok.Data;

import java.util.List;

/**
 * 单次体检聚合结果。
 */
@Data
public class PatientExamSessionResponse {

    private String studyId;

    private String orderCode;

    private String examTime;

    private String packageCode;

    private String packageName;

    private String abnormalSummary;

    private String finalConclusion;

    /**
     * 异常检查项数量。
     *
     * <p>按细项 {@code abnormalFlag = 1} 统计。
     */
    private Integer abnormalCount;

    private List<PatientExamDepartmentResultResponse> departments;
}
