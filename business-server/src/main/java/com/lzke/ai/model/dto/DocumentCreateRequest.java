package com.lzke.ai.model.dto;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

import java.util.List;

/**
 * 文档创建请求
 */
@Data
public class DocumentCreateRequest {

    @NotBlank(message = "文档标题不能为空")
    private String title;

    private String content;
    private String category;
    private List<String> tags;
    private String source;
}
