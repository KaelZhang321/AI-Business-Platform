package com.lzke.ai.application.exam.dto;

import lombok.Data;

/**
 * 患者基础信息。
 */
@Data
public class PatientExamPatientInfoResponse {

    private String studyId;

    private String patientName;

    private String gender;

    private String idCard;

    private String mobile;

    private String patientNo;
}
