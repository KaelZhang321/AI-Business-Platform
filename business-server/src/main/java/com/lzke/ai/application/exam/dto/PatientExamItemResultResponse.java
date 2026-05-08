package com.lzke.ai.application.exam.dto;

import lombok.Data;

/**
 * 体检细项结果。
 */
@Data
public class PatientExamItemResultResponse {

    private String majorItemCode;

    private String majorItemName;

    private String itemCode;

    private String itemName;

    private String itemNameEn;

    private String resultValue;

    private String unit;

    private String referenceRange;

    private String abnormalFlag;
}
