package com.lzke.ai.model.vo;

import lombok.Data;

import java.util.List;

/**
 * 文档视图对象
 */
@Data
public class DocumentVO {

    private String id;
    private String title;
    private String category;
    private List<String> tags;
    private String source;
    private Integer chunkCount;
    private String status;
    private String createdAt;
    private String updatedAt;
}
