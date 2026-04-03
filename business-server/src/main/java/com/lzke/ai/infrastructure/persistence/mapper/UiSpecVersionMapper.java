package com.lzke.ai.infrastructure.persistence.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.lzke.ai.domain.entity.UiSpecVersion;
import org.apache.ibatis.annotations.Mapper;

/**
 * UI Builder 发布版本 Mapper。
 */
@Mapper
public interface UiSpecVersionMapper extends BaseMapper<UiSpecVersion> {
}
