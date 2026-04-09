package com.lzke.ai.application.dto;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

/**
 * json-render 表单多接口提交响应。
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
public class UiJsonRenderSubmitResponse {

    private String flowNum;
    private boolean success;
    private List<UiJsonRenderSubmitActionResponse> results;
}
