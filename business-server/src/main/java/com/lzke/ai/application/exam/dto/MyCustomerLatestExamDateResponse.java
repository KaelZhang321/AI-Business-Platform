package com.lzke.ai.application.exam.dto;

import lombok.Data;

/**
 * 加密身份证与最近体检日期映射。
 */
@Data
public class MyCustomerLatestExamDateResponse {

    /**
     * 加密身份证号。
     */
    private String encryptedIdCard;

    /**
     * 最近一次体检日期，格式 yyyy-MM-dd。
     */
    private String latestExamDate;
}
