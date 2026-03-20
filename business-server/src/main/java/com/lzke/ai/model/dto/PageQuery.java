package com.lzke.ai.model.dto;

import lombok.Data;

/**
 * 分页查询基类
 */
@Data
public class PageQuery {

    private int page = 1;
    private int size = 20;

    public int getOffset() {
        return (page - 1) * size;
    }
}
