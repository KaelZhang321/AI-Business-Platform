package com.lzke.ai.application.dto;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.Map;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class UiPagePreviewResponse {

    private String pageId;
    private String rootNodeId;
    private Map<String, Object> spec;
}
