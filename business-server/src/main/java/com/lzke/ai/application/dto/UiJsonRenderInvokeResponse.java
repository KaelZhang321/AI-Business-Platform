package com.lzke.ai.application.dto;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.Map;

/**
 * 运行时“调用接口并转 json-render”响应。
 *
 * <p>返回值同时包含：
 *
 * <ul>
 *     <li>接口原始响应体的解析结果</li>
 *     <li>基于响应体生成的 json-render Spec</li>
 *     <li>本次运行时调用写入的日志 ID</li>
 * </ul>
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
public class UiJsonRenderInvokeResponse {

    private String endpointId;
    private String roleId;
    private String flowNum;
    private String flowLogId;
    private Object responseBody;
    private Map<String, Object> jsonRender;
}
