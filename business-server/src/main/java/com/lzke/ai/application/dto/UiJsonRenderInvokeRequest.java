package com.lzke.ai.application.dto;

import lombok.Data;
import lombok.EqualsAndHashCode;

/**
 * 运行时“调用接口并转 json-render”请求。
 *
 * <p>该请求基于普通运行时调用请求扩展了 `roleId`，用于在转换 json-render 时
 * 叠加 `ui_api_endpoint_roles.field_orchestration` 作为角色侧覆盖配置。
 */
@Data
@EqualsAndHashCode(callSuper = true)
public class UiJsonRenderInvokeRequest extends UiApiInvokeRequest {

    /**
     * 角色 ID，可为空。
     *
     * <p>当同一个接口在不同角色下需要不同的字段编排时，传入该值后会自动读取角色级覆盖配置。
     */
    private String roleId;
}
