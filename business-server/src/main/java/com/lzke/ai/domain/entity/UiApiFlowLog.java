package com.lzke.ai.domain.entity;

import com.baomidou.mybatisplus.annotation.FieldFill;
import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.OffsetDateTime;

/**
 * UI Builder 运行时接口调用日志实体。
 *
 * <p>对应 `ui_api_flow_logs`，用于记录通过 runtime invoke 接口发起的真实接口调用快照。
 */
@Data
@TableName("ui_api_flow_logs")
public class UiApiFlowLog {

    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    private String flowNum;
    private String endpointId;
    private String requestUrl;
    private String requestHeaders;
    private String requestQuery;
    private String requestBody;
    private Integer responseStatus;
    private String responseHeaders;
    private String responseBody;
    private String invokeStatus;
    private String errorMessage;
    private String createdBy;
    private String createdByName;

    @TableField(fill = FieldFill.INSERT)
    private OffsetDateTime createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private OffsetDateTime updatedAt;
}
