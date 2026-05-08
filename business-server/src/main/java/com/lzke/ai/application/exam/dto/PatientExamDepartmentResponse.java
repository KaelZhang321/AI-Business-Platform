package com.lzke.ai.application.exam.dto;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * 体检科室下拉项。
 *
 * <p>前端做多选部门筛选时只需要编码和名称，因此单独提供一份轻量响应对象，
 * 避免把内部用于动态 SQL 的表名和字段表达式直接暴露出去。
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
public class PatientExamDepartmentResponse {

    /**
     * 科室编码，例如 HY / US。
     */
    private String departmentCode;

    /**
     * 科室名称，例如 化验室 / 彩超室。
     */
    private String departmentName;
}
