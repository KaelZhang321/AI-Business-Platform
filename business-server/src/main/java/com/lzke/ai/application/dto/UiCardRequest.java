package com.lzke.ai.application.dto;

import lombok.Data;

/**
 * UI Builder 卡片新增/更新请求。
 */
@Data
public class UiCardRequest {

    private String name;
    private String code;
    private String description;
    private String cardType;
    private String status;
    private String createdBy;
}
