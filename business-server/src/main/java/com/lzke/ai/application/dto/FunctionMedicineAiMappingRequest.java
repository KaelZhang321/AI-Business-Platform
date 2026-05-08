package com.lzke.ai.application.dto;

import lombok.Data;

/**
 * 功能医学 AI 推荐方案映射新增/更新请求。
 */
@Data
public class FunctionMedicineAiMappingRequest {

    private Integer serialNo;

    private String systemName;

    private String projectName;

    private String indicatorCode;

    private String indicatorName;

    private String examProjectName;

    private String idealRange;

    private String packageVersion;

    private String priceText;

    private String coreEffect;

    private String indications;

    private String contraindications;

    private String remark;

    private String status;

    private String sourceSheetName;

    private Integer sourceRowNo;
}
