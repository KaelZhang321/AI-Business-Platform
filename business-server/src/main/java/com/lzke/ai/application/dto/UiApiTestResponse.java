package com.lzke.ai.application.dto;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.Map;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class UiApiTestResponse {

    private String requestUrl;
    private Integer responseStatus;
    private Map<String, Object> responseHeaders;
    private Object responseBody;
    private Boolean success;
    private String errorMessage;
}
