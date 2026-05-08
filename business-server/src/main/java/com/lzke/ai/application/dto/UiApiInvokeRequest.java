package com.lzke.ai.application.dto;

import lombok.Data;

import java.util.Map;

/**
 * UI Builder 运行时接口调用请求。
 *
 * <p>该请求对象面向 `/runtime/endpoints/{endpointId}/invoke`，
 * 用于承载流程号、请求参数和调用人信息。
 */
@Data
public class UiApiInvokeRequest {

    private String flowNum = System.currentTimeMillis() + "";
    private Map<String, Object> headers;
    private Map<String, Object> queryParams;
    private Object body;
    private String createdBy;
    private String createdByName;
    private Boolean useSampleWhenEmpty = true;
}
