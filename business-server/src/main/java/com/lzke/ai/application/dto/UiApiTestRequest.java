package com.lzke.ai.application.dto;

import lombok.Data;

import java.util.Map;

@Data
public class UiApiTestRequest {

    private Map<String, Object> headers;
    private Map<String, Object> queryParams;
    private Object body;
    private String createdBy;
}
