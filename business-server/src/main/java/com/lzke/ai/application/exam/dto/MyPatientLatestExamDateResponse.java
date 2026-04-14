package com.lzke.ai.application.exam.dto;

import lombok.Data;

/**
 * 患者最近一次体检日期映射。
 */
@Data
public class MyPatientLatestExamDateResponse {

    /**
     * 明文身份证号。
     */
    private String idCard;

    /**
     * 最近一次体检日期，格式 yyyy-MM-dd。
     */
    private String latestExamDate;
}
