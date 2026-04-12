package com.lzke.ai.application.exam.dto;

import lombok.Data;

import java.util.List;

/**
 * 单次体检结果查询条件。
 */
@Data
public class PatientExamResultQueryRequest {

    /**
     * 体检主单号。
     */
    private String studyId;

    /**
     * 前端选择的科室编码列表，不传则查询当前体检的全部科室结果。
     */
    private List<String> departmentCodes;
}
