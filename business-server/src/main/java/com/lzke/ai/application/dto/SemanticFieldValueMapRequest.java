package com.lzke.ai.application.dto;

import lombok.Data;

/**
 * 语义字段值映射请求。
 */
@Data
public class SemanticFieldValueMapRequest {

    private String standardKey;
    private String apiId;
    private String standardValue;
    private String rawValue;
    private Integer sortOrder;
}
