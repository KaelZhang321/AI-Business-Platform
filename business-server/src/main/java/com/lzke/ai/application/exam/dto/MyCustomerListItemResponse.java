package com.lzke.ai.application.exam.dto;

import lombok.Data;

/**
 * 我的客户列表项。
 *
 * <p>该对象面向前端列表展示，保留常用客户字段，并补一列最近体检日期。
 */
@Data
public class MyCustomerListItemResponse {

    /**
     * 客户ID。
     */
    private String customerId;

    /**
     * 客户姓名。
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
     * 上游返回的加密身份证。
     */
    private String encryptedIdCard;

    /**
     * 脱敏身份证。
     */
    private String idCardObfuscated;

    /**
     * 上游返回的加密手机号。
     */
    private String encryptedPhone;

    /**
     * 脱敏手机号。
     */
    private String phoneObfuscated;

    /**
     * 客户类型。
     */
    private String typeName;

    /**
     * 门店名称。
     */
    private String storeName;

    /**
     * 主市场老师。
     */
    private String mainTeacherName;

    /**
     * 分总。
     */
    private String subTeacherName;

    /**
     * 最近一次体检日期，格式 yyyy-MM-dd。
     */
    private String latestExamDate;
}
