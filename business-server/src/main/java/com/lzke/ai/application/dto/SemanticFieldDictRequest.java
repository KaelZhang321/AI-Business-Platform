package com.lzke.ai.application.dto;

import lombok.Data;

/**
 * 语义字段字典请求。
 */
@Data
public class SemanticFieldDictRequest {

    private String standardKey;
    private String label;
    private String fieldType;
    private String category;
    private String valueMap;
    private String description;
    private Integer isActive;
}
