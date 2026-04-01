package com.lzke.ai.domain.entity;

import com.baomidou.mybatisplus.annotation.FieldFill;
import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.OffsetDateTime;

/**
 * UI Builder 接口联调日志实体。
 *
 * <p>对应 `ui_api_test_logs`，用于记录每次联调的请求快照和响应快照。
 */
@Data
@TableName("ui_api_test_logs")
public class UiApiTestLog {

    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    private String endpointId;
    private String requestUrl;
    private String requestHeaders;
    private String requestQuery;
    private String requestBody;
    private Integer responseStatus;
    private String responseHeaders;
    private String responseBody;
    private Integer successFlag;
    private String errorMessage;
    private String createdBy;

    @TableField(fill = FieldFill.INSERT)
    private OffsetDateTime createdAt;
}
