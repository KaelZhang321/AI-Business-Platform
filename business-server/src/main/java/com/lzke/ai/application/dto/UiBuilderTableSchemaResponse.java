package com.lzke.ai.application.dto;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class UiBuilderTableSchemaResponse {

    private String name;
    private String purpose;
    private List<UiBuilderFieldResponse> fields;
}
