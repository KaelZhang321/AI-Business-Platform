package com.lzke.ai.application.dto;

import lombok.Data;

@Data
public class UiNodeBindingRequest {

    private String endpointId;
    private String bindingType;
    private String targetProp;
    private String sourcePath;
    private String transformScript;
    private String defaultValue;
    private Boolean requiredFlag;
}
