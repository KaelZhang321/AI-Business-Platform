package com.lzke.ai.application.exam.dto;

import lombok.Data;

/**
 * 患者体检查询基础条件。
 *
 * <p>用于先锁定某个患者，再去查询该患者的体检记录或单次体检结果。
 */
@Data
public class PatientExamPatientQueryRequest {

    /**
     * 体检单号 / 订单号。
     */
    private String orderCode;

    /**
     * 患者姓名。
     */
    private String patientName;

    /**
     * 身份证号。
     */
    private String idCard;

    /**
     * 手机号。
     */
    private String mobile;

    /**
     * 会员号 / 病历号 / 客户编码等院内主索引。
     */
    private String patientNo;

    /**
     * 体检开始时间，建议前端按 yyyy-MM-dd HH:mm:ss 传入。
     */
    private String startTime;

    /**
     * 体检结束时间，建议前端按 yyyy-MM-dd HH:mm:ss 传入。
     */
    private String endTime;
}
