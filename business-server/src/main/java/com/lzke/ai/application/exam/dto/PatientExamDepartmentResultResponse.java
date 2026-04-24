package com.lzke.ai.application.exam.dto;

import lombok.Data;

import java.util.List;

/**
 * 单次体检下的科室聚合结果。
 */
@Data
public class PatientExamDepartmentResultResponse {

    private String departmentCode;

    private String departmentName;

    private String sourceTable;

    private List<PatientExamItemResultResponse> items;
}
