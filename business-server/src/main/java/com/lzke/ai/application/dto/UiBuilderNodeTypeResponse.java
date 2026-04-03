package com.lzke.ai.application.dto;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class UiBuilderNodeTypeResponse {

    private String type;
    private String description;
    private Boolean supportsChildren;
    private List<String> keyProps;
}
