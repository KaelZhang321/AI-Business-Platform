package com.lzke.ai.application.rule.dto;

import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.lzke.ai.application.dto.PageQuery;

import lombok.Data;

@Data
public class RuleQueryDTO extends PageQuery implements java.io.Serializable{

	private static final long serialVersionUID = 1L;
	
	
	private Long id;

    public <T> Page<T> build() {
        return new Page<>(getPage(), getSize());
    }
	
}
