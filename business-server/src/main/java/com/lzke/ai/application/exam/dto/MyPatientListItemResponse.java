package com.lzke.ai.application.exam.dto;

import lombok.Data;

/**
 * 我的患者列表项。
 */
@Data
public class MyPatientListItemResponse {

    /**
     * 客户主键。
     */
    private String customerMasterId;

    /**
     * 患者姓名。
     */
    private String patientName;

    /**
     * 性别。
     */
    private String gender;

    /**
     * 年龄。
     */
    private Integer age;

    /**
     * 身份证号。
     */
    private String idCard;

    /**
     * 联系电话。
     */
    private String mobile;

    /**
     * 最近一次体检时间，格式 yyyy-MM-dd。
     */
    private String latestExamDate;
}
