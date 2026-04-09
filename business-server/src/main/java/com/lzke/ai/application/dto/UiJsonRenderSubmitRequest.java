package com.lzke.ai.application.dto;

import lombok.Data;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * json-render 表单提交请求。
 *
 * <p>该请求面向“一个表单驱动多个接口提交”的场景：
 *
 * <ul>
 *     <li>`semanticValues` 承载前端按标准语义字段提交的值</li>
 *     <li>`actions` 描述需要依次调用哪些接口</li>
 * </ul>
 *
 * <p>服务端会先把标准语义字段值转换成每个接口所需的原始字段和值，再调用真实接口。
 */
@Data
public class UiJsonRenderSubmitRequest {

    private String flowNum;
    private String createdBy;
    private String createdByName;
    private Map<String, Object> semanticValues = new LinkedHashMap<>();
    private List<UiJsonRenderSubmitActionRequest> actions;
}
