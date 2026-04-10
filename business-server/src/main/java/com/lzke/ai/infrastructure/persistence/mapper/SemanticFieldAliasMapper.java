package com.lzke.ai.infrastructure.persistence.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.lzke.ai.domain.entity.SemanticFieldAlias;
import org.apache.ibatis.annotations.Mapper;

/**
 * 语义字段别名 Mapper。
 */
@Mapper
public interface SemanticFieldAliasMapper extends BaseMapper<SemanticFieldAlias> {
}
