package com.lzke.ai.application.exam.dto;

import lombok.Data;

/**
 * 患者体检结果明细行。
 *
 * <p>该对象用于承接跨科室 UNION ALL 后的统一输出字段。
 * 某些字段来自结果表本身，某些字段来自基础字典表关联。
 */
@Data
public class PatientExamResultItemResponse {

    /**
     * 来源科室编码。
     */
    private String departmentCode;

    /**
     * 来源科室名称。
     */
    private String departmentName;

    /**
     * 动态来源表名，便于排查问题。
     */
    private String sourceTable;

    /**
     * 订单号 / 体检单号。
     */
    private String orderCode;

    /**
     * 体检主单号。
     */
    private String studyId;

    /**
     * 患者姓名。
     */
    private String patientName;

    /**
     * 性别。
     */
    private String gender;

    /**
     * 身份证号。
     */
    private String idCard;

    /**
     * 手机号。
     */
    private String mobile;

    /**
     * 患者编号 / 会员号。
     */
    private String patientNo;

    /**
     * 套餐编码。
     */
    private String packageCode;

    /**
     * 套餐名称。
     */
    private String packageName;

    /**
     * 大项编码。
     */
    private String majorItemCode;

    /**
     * 大项名称。
     */
    private String majorItemName;

    /**
     * 检查项编码。
     */
    private String itemCode;

    /**
     * 检查项名称。
     */
    private String itemName;

    /**
     * 检查项英文名或扩展名。
     */
    private String itemNameEn;

    /**
     * 结果值。
     */
    private String resultValue;

    /**
     * 结果单位。
     */
    private String unit;

    /**
     * 参考范围。
     */
    private String referenceRange;

    /**
     * 异常标志。
     */
    private String abnormalFlag;

    /**
     * 检查/报告时间。
     */
    private String examTime;

    /**
     * 异常结果汇总。
     */
    private String abnormalSummary;

    /**
     * 总检结论。
     */
    private String finalConclusion;
}
