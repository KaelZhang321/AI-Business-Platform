package com.lzke.ai.infrastructure.persistence.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.lzke.ai.domain.entity.UiApiTestLog;
import org.apache.ibatis.annotations.Mapper;

/**
 * UI Builder 接口联调日志 Mapper。
 */
@Mapper
public interface UiApiTestLogMapper extends BaseMapper<UiApiTestLog> {
}
