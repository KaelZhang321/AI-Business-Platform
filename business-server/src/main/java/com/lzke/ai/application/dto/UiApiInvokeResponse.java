package com.lzke.ai.application.dto;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.Map;

/**
 * UI Builder 运行时接口调用响应。
 *
 * <p>返回一次真实接口调用的结果，以及本次调用生成的运行时日志 ID。
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
public class UiApiInvokeResponse {

    private String logId;
    private String endpointId;
    private String endpointName;
    private String flowNum;
    private String requestUrl;
    private Integer responseStatus;
    private Map<String, Object> responseHeaders;
    private Object responseBody;
    private Boolean success;
    private String errorMessage;
}
