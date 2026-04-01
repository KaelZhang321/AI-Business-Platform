package com.lzke.ai.application.dto;

import lombok.Data;

/**
 * OpenAPI 导入请求。
 *
 * <p>当前支持三种导入方式：
 *
 * <ul>
 *     <li>直接传完整 OpenAPI/Swagger JSON 文本到 {@link #document}</li>
 *     <li>传 Swagger/OpenAPI 文档地址到 {@link #documentUrl}</li>
 *     <li>两者都不传时，后端回退使用接口源上配置的 `docUrl`</li>
 * </ul>
 */
@Data
public class UiOpenApiImportRequest {

    /**
     * 直接传入的 OpenAPI 文档内容，通常是 JSON 字符串。
     */
    private String document;

    /**
     * OpenAPI/Swagger 文档地址。
     *
     * <p>推荐使用可直接返回 JSON 的地址，例如 `/v3/api-docs`。
     */
    private String documentUrl;
}
