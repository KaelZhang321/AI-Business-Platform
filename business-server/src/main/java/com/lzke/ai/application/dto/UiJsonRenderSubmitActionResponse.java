package com.lzke.ai.application.dto;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * json-render 表单提交中的单步接口执行结果。
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
public class UiJsonRenderSubmitActionResponse {

    private String endpointId;
    private String roleId;
    private String flowLogId;
    private String requestUrl;
    private boolean success;
    private Object responseBody;
    private String errorMessage;
}
