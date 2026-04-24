package com.lzke.ai.application.dto;

import lombok.Data;

@Data
public class UiApiSourceRequest {

    private String name;
    private String code;
    private String description;
    private String sourceType;
    private String baseUrl;
    private String docUrl;
    private String authType;
    private String authConfig;
    private String defaultHeaders;
    private String env;
    private String status;
    private String createdBy;
}
