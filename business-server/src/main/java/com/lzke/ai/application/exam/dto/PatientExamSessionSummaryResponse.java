package com.lzke.ai.application.exam.dto;

import lombok.Data;

/**
 * 患者单次体检摘要。
 */
@Data
public class PatientExamSessionSummaryResponse {

    private String studyId;

    private String orderCode;

    private String examTime;

    private String packageCode;

    private String packageName;

    private String abnormalSummary;

    private String finalConclusion;
}
