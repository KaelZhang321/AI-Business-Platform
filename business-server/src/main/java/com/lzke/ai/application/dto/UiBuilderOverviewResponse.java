package com.lzke.ai.application.dto;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class UiBuilderOverviewResponse {

    private String moduleName;
    private String description;
    private List<UiBuilderFeatureResponse> features;
    private List<String> workflowSteps;
    private List<UiBuilderAuthTypeResponse> authTypes;
    private List<UiBuilderNodeTypeResponse> nodeTypes;
    private List<UiBuilderTableSchemaResponse> tables;
}