package com.lzke.ai.application.dto;

import lombok.Data;

import java.util.List;

/**
 * UI Builder 卡片绑定接口请求。
 */
@Data
public class UiCardEndpointBindRequest {

    private List<String> endpointIds;
    private Boolean replaceAll;
}
