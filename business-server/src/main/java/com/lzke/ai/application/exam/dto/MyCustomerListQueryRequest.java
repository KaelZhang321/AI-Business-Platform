package com.lzke.ai.application.exam.dto;

import com.lzke.ai.application.dto.PageQuery;
import lombok.Data;
import lombok.EqualsAndHashCode;

import java.util.Map;

/**
 * 我的客户列表查询条件。
 *
 * <p>该接口实际透传到 UI Builder 已配置好的客户列表接口，
 * 这里保留分页参数，并允许前端按需传扩展 query/body 参数。
 */
@Data
@EqualsAndHashCode(callSuper = true)
public class MyCustomerListQueryRequest extends PageQuery {

    /**
     * 透传给上游接口的查询参数。
     */
    private Map<String, Object> queryParams;

    /**
     * 透传给上游接口的请求体。
     */
    private Map<String, Object> body;
}
