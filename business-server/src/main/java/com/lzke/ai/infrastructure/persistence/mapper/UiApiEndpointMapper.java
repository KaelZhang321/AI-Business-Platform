package com.lzke.ai.infrastructure.persistence.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.lzke.ai.domain.entity.UiApiEndpoint;
import org.apache.ibatis.annotations.Mapper;

/**
 * UI Builder 接口定义 Mapper。
 */
@Mapper
public interface UiApiEndpointMapper extends BaseMapper<UiApiEndpoint> {
}
