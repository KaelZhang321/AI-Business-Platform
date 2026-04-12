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

    private List<PatientExamDepartmentResultResponse> departments;
}
