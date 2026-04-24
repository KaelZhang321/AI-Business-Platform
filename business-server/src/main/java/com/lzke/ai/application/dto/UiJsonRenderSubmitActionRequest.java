package com.lzke.ai.application.dto;

import lombok.Data;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * json-render 表单提交中的单步接口动作定义。
 *
 * <p>一个表单可能会拆分成多个接口调用步骤，每个步骤都需要显式声明：
 *
 * <ul>
 *     <li>调用哪个 endpoint</li>
 *     <li>哪些标准语义字段需要落到 query/body/header</li>
 *     <li>是否带上一些固定参数</li>
 * </ul>
 *
 * <p>真正的“标准语义值 -> 接口原始字段值”转换由
 * `UiJsonRenderTransformService` 结合 `semantic_field_alias` 与
 * `semantic_field_value_map` 自动完成。
 */
@Data
public class UiJsonRenderSubmitActionRequest {

    private String endpointId;
    private String roleId;
    private List<String> queryKeys;
    private List<String> bodyKeys;
    private List<String> headerKeys;
    private Map<String, Object> staticQueryParams = new LinkedHashMap<>();
    private Map<String, Object> staticBody = new LinkedHashMap<>();
    private Map<String, Object> staticHeaders = new LinkedHashMap<>();
    private Boolean useSampleWhenEmpty = true;
}
