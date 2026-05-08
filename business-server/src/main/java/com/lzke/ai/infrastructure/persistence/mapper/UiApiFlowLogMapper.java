package com.lzke.ai.infrastructure.persistence.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.lzke.ai.domain.entity.UiApiFlowLog;
import org.apache.ibatis.annotations.Mapper;

/**
 * UI Builder 运行时接口调用日志 Mapper。
 */
@Mapper
public interface UiApiFlowLogMapper extends BaseMapper<UiApiFlowLog> {
}
