package com.lzke.ai.model.dto;

import lombok.Data;
import lombok.EqualsAndHashCode;

/**
 * 待办聚合查询参数
 */
@Data
@EqualsAndHashCode(callSuper = true)
public class TaskAggregateQuery extends PageQuery {

    private String userId;
    private String status;
    private String sourceSystem;
    private String priority;
}
