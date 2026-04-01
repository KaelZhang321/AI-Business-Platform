package com.lzke.ai.application.dto;

import lombok.Data;

@Data
public class UiApiEndpointRequest {

    private String sourceId;
    private String tagId;
    private String name;
    private String path;
    private String method;
    private String summary;
    private String requestContentType;
    private String requestSchema;
    private String responseSchema;
    private String sampleRequest;
    private String sampleResponse;
    private String status;
}
