package com.lzke.ai.application.exam.dto;

import com.lzke.ai.application.dto.PageQuery;
import lombok.Data;
import lombok.EqualsAndHashCode;

/**
 * 患者体检记录分页查询条件。
 */
@Data
@EqualsAndHashCode(callSuper = true)
public class PatientExamSessionQueryRequest extends PageQuery {

    private String orderCode;

    private String patientName;

    private String idCard;

    private String mobile;

    private String patientNo;

    private String startTime;

    private String endTime;
}
