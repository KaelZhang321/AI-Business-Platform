package com.lzke.ai.infrastructure.persistence.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.lzke.ai.domain.entity.ApiKey;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface ApiKeyMapper extends BaseMapper<ApiKey> {
}
