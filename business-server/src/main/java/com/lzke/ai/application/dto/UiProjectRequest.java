package com.lzke.ai.application.dto;

import lombok.Data;

@Data
public class UiProjectRequest {

    private String name;
    private String code;
    private String description;
    private String category;
    private String status;
    private String createdBy;
}
