package com.lzke.ai.application.exam.dto;

import lombok.Data;

import java.util.List;

/**
 * 批量体检结果查询条件。
 *
 * <p>前端通常会先通过体检记录分页接口拿到若干次体检，再按 studyId 批量拉取报告详情。
 */
@Data
public class PatientExamBatchResultQueryRequest {

    /**
     * 身份证号。
     *
     * <p>传入后会按身份证号查询该患者全部体检信息。
     */
    private String idCard;

    /**
     * 需要查询的体检主单号列表，最多10个。
     */
    private List<String> studyIds;

    /**
     * 可选科室编码列表，不传则查询全部科室。
     */
    private List<String> departmentCodes;
}
