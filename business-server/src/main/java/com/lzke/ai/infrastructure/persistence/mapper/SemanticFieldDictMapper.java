package com.lzke.ai.infrastructure.persistence.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.lzke.ai.domain.entity.SemanticFieldDict;
import org.apache.ibatis.annotations.Mapper;

/**
 * 语义字段字典 Mapper。
 */
@Mapper
public interface SemanticFieldDictMapper extends BaseMapper<SemanticFieldDict> {
}
