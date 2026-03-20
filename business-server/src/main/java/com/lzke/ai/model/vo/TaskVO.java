package com.lzke.ai.model.vo;

import lombok.Data;

/**
 * 任务视图对象
 */
@Data
public class TaskVO {

    private String id;
    private String sourceSystem;
    private String sourceId;
    private String title;
    private String description;
    private String status;
    private String priority;
    private String deadline;
    private String externalUrl;
    private String error;
}
