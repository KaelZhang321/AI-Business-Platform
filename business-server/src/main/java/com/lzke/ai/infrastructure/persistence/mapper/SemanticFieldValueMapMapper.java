package com.lzke.ai.infrastructure.persistence.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.lzke.ai.domain.entity.SemanticFieldValueMap;
import org.apache.ibatis.annotations.Mapper;

/**
 * 语义字段值映射 Mapper。
 */
@Mapper
public interface SemanticFieldValueMapMapper extends BaseMapper<SemanticFieldValueMap> {
}
