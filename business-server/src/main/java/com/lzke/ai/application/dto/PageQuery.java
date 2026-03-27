package com.lzke.ai.application.dto;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import lombok.Data;

/**
 * 分页查询基类
 */
@Data
public class PageQuery {

    @Min(value = 1, message = "页码不能小于1")
    private int page = 1;

    @Min(value = 1, message = "每页条数不能小于1")
    @Max(value = 100, message = "每页条数不能超过100")
    private int size = 20;

    public int getOffset() {
        return (page - 1) * size;
    }
}
