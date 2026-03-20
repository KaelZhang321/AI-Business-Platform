package com.lzke.ai.model.dto;

import lombok.Data;
import lombok.EqualsAndHashCode;

/**
 * 审计日志查询参数
 */
@Data
@EqualsAndHashCode(callSuper = true)
public class AuditLogQuery extends PageQuery {

    private String userId;
    private String intent;
    private String status;
}
