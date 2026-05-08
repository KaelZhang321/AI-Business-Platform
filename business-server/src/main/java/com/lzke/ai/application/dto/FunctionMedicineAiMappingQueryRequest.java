package com.lzke.ai.application.dto;

import lombok.Data;
import lombok.EqualsAndHashCode;

/**
 * 功能医学 AI 推荐方案映射分页查询条件。
 */
@Data
@EqualsAndHashCode(callSuper = true)
public class FunctionMedicineAiMappingQueryRequest extends PageQuery {

    private String systemName;

    private String projectName;

    private String packageVersion;

    private String indicatorCode;

    private String indicatorName;

    private String status;
}
