package com.lzke.ai.application.dto;

import lombok.Data;

@Data
public class UiPageNodeRequest {

    private String parentId;
    private String nodeKey;
    private String nodeType;
    private String nodeName;
    private Integer sortOrder;
    private String slotName;
    private String propsConfig;
    private String styleConfig;
    private String status;
}
