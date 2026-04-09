package com.lzke.ai.application.dto;

import lombok.Data;

/**
 * 语义字段别名请求。
 */
@Data
public class SemanticFieldAliasRequest {

    private String standardKey;
    private String alias;
    private String apiId;
    private String source;
}
