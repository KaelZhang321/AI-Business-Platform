package com.lzke.ai.infrastructure.persistence.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.lzke.ai.domain.entity.UiCardEndpointRelation;
import org.apache.ibatis.annotations.Mapper;

/**
 * UI Builder 卡片与接口关系 Mapper。
 */
@Mapper
public interface UiCardEndpointRelationMapper extends BaseMapper<UiCardEndpointRelation> {
}
