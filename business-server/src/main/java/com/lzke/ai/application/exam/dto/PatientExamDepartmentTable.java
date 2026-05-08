package com.lzke.ai.application.exam.dto;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * 参与动态查询的科室表信息。
 *
 * <p>由于结果表是按科室编码动态分表的：
 * `ods_tj_${ksbm小写}b`
 * 所以前置服务会先把待查询的科室编码解析成安全表名，再传入 MyBatis XML 做 UNION ALL。
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
public class PatientExamDepartmentTable {

    /**
     * 科室编码，例如 HY / US。
     */
    private String departmentCode;

    /**
     * 科室名称。
     */
    private String departmentName;

    /**
     * 安全表名，例如 ods_tj_hyb。
     */
    private String tableName;

    /**
     * 订单号字段表达式，例如 t.`OrderCode`。
     */
    private String orderCodeExpr;

    /**
     * 患者姓名字段表达式。
     */
    private String patientNameExpr;

    /**
     * 身份证号字段表达式。
     */
    private String idCardExpr;

    /**
     * 手机号字段表达式。
     */
    private String mobileExpr;

    /**
     * 患者编号字段表达式。
     */
    private String patientNoExpr;

    /**
     * 检查项编码字段表达式。
     */
    private String itemCodeExpr;

    /**
     * 大项编码字段表达式。
     */
    private String majorItemCodeExpr;

    /**
     * 检查项名称字段表达式。
     */
    private String itemNameExpr;

    /**
     * 检查项扩展名称字段表达式。
     */
    private String itemNameEnExpr;

    /**
     * 结果值字段表达式。
     */
    private String resultValueExpr;

    /**
     * 单位字段表达式。
     */
    private String unitExpr;

    /**
     * 参考范围字段表达式。
     */
    private String referenceRangeExpr;

    /**
     * 异常标志字段表达式。
     */
    private String abnormalFlagExpr;

    /**
     * 时间字段表达式。
     */
    private String examTimeExpr;
}
