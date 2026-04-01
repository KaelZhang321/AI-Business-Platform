package com.lzke.ai.application.dto;

import lombok.Data;

@Data
public class UiPageRequest {

    private String name;
    private String code;
    private String title;
    private String routePath;
    private String rootNodeId;
    private String layoutType;
    private String status;
}
