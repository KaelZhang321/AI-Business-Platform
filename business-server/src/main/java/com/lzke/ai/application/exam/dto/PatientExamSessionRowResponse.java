package com.lzke.ai.application.exam.dto;

import lombok.Data;

/**
 * 体检主记录行。
 *
 * <p>该对象只用于 Mapper 承接主表分页查询结果，再由服务层组装成层级响应。
 */
@Data
public class PatientExamSessionRowResponse {

    private String studyId;

    private String orderCode;

    private String patientName;

    private String gender;

    private String idCard;

    private String mobile;

    private String patientNo;

    private String packageCode;

    private String packageName;

    private String examTime;

    private String abnormalSummary;

    private String finalConclusion;
}
